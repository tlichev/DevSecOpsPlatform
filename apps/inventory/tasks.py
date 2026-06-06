import logging
import socket
import subprocess
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _ping(ip: str, timeout: int = 2) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Windows ping fallback
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), ip],
                capture_output=True,
                timeout=timeout + 2,
            )
            return result.returncode == 0
        except Exception:
            return False


def _snmp_get_hostname(ip: str, community: str = "public") -> str:
    """Try to get sysName via SNMP."""
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity,
        )
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysName", 0)),
        )
        error_indication, error_status, _, var_binds = next(iterator)
        if not error_indication and not error_status:
            return str(var_binds[0][1])
    except Exception as exc:
        logger.debug("SNMP get hostname failed for %s: %s", ip, exc)
    return ""


def _resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return ""


@shared_task(bind=True, queue="discovery", max_retries=1)
def run_discovery(self, job_id: int):
    from .models import Device, DiscoveryJob, DeviceStatus

    job = DiscoveryJob.objects.get(pk=job_id)
    job.status = DiscoveryJob.Status.RUNNING
    job.started_at = datetime.now(tz=timezone.utc)
    job.save(update_fields=["status", "started_at"])

    log_lines = [f"[{datetime.now(tz=timezone.utc)}] Starting discovery on {job.subnet}"]
    found = 0
    added = 0

    try:
        import ipaddress
        network = ipaddress.ip_network(job.subnet, strict=False)
        hosts = list(network.hosts())

        for host in hosts:
            ip = str(host)
            if not _ping(ip):
                continue

            found += 1
            log_lines.append(f"[ALIVE] {ip}")

            if Device.objects.filter(ip_address=ip).exists():
                log_lines.append(f"  → already in inventory, skipping")
                continue

            snmp_name = _snmp_get_hostname(ip, settings.SNMP_COMMUNITY)
            dns_name = _resolve_hostname(ip)
            hostname = snmp_name or dns_name or ip.replace(".", "-")

            Device.objects.create(
                hostname=hostname,
                ip_address=ip,
                status=DeviceStatus.ONLINE,
                discovered_at=datetime.now(tz=timezone.utc),
                snmp_community=settings.SNMP_COMMUNITY,
            )
            added += 1
            log_lines.append(f"  → added as '{hostname}'")

        job.status = DiscoveryJob.Status.COMPLETED
    except Exception as exc:
        logger.exception("Discovery job %s failed", job_id)
        log_lines.append(f"[ERROR] {exc}")
        job.status = DiscoveryJob.Status.FAILED

    job.completed_at = datetime.now(tz=timezone.utc)
    job.devices_found = found
    job.devices_added = added
    job.log = "\n".join(log_lines)
    job.save(update_fields=["status", "completed_at", "devices_found", "devices_added", "log"])

    return {"found": found, "added": added}


@shared_task(bind=True, queue="discovery")
def check_device_reachability(self, device_id: int):
    from .models import Device, DeviceStatus

    device = Device.objects.get(pk=device_id)
    reachable = _ping(device.ip_address)
    new_status = DeviceStatus.ONLINE if reachable else DeviceStatus.OFFLINE
    Device.objects.filter(pk=device_id).update(status=new_status)
    logger.info("Device %s (%s) status: %s", device.hostname, device.ip_address, new_status)
    return {"device_id": device_id, "status": new_status}


@shared_task(queue="discovery")
def refresh_all_device_status():
    """Periodic task: ping every device and update status."""
    from .models import Device

    device_ids = list(Device.objects.values_list("id", flat=True))
    for device_id in device_ids:
        check_device_reachability.delay(device_id)
    return {"queued": len(device_ids)}
