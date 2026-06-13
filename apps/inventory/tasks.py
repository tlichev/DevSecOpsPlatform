import subprocess
import logging
import ipaddress

from celery import shared_task, group
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ── ICMP helper ────────────────────────────────────────────────────────────────
def _ping(ip: str, count: int = 1, timeout: int = 2) -> bool:
    """Returns True if the host responds to ICMP echo (Linux ping syntax)."""
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', str(timeout), str(ip)],
            capture_output=True,
            timeout=timeout * count + 3,
        )
        return result.returncode == 0
    except Exception:
        return False


# ── SNMP sysName helper ────────────────────────────────────────────────────────
def _snmp_get_sysname(ip: str, community: str = 'public', timeout: int = 3) -> str | None:
    """Attempt SNMP v2c GET for sysName.0 (OID 1.3.6.1.2.1.1.5.0)."""
    try:
        import puresnmp
        result = puresnmp.get(ip, community, '1.3.6.1.2.1.1.5.0', port=161)
        return str(result).strip() if result else None
    except Exception:
        return None


# ── Per-device poll ────────────────────────────────────────────────────────────
@shared_task(bind=True, name='inventory.poll_device', queue='monitoring',
             max_retries=2, default_retry_delay=30)
def poll_device(self, device_id: int) -> dict:
    """ICMP + SNMP status poll for a single device. Updates Device.status."""
    from .models import Device
    try:
        device = Device.objects.get(pk=device_id)
        is_up = _ping(device.ip_address)

        if is_up:
            device.mark_seen()
        else:
            device.mark_down()

        logger.debug('Polled %s (%s): %s', device.hostname, device.ip_address,
                     'up' if is_up else 'down')
        return {'device': device.hostname, 'status': device.status, 'ip': device.ip_address}

    except Device.DoesNotExist:
        logger.warning('poll_device: device %s not found', device_id)
        return {'error': 'not_found', 'device_id': device_id}
    except Exception as exc:
        logger.error('poll_device: error for %s: %s', device_id, exc)
        raise self.retry(exc=exc)


# ── Poll all known devices ─────────────────────────────────────────────────────
@shared_task(name='inventory.poll_all_devices', queue='monitoring')
def poll_all_devices() -> str:
    """Dispatch concurrent polls for every registered device."""
    from .models import Device
    device_ids = list(Device.objects.values_list('pk', flat=True))
    if not device_ids:
        return 'No devices registered.'
    job = group(poll_device.s(pk) for pk in device_ids)
    job.apply_async()
    return f'Dispatched polls for {len(device_ids)} devices.'


# ── Network discovery ──────────────────────────────────────────────────────────
@shared_task(name='inventory.discover_network', queue='discovery')
def discover_network() -> dict:
    """
    Scan MGMT_NETWORK (default 192.168.100.0/24) for live hosts.
    - Pings every host in the subnet.
    - For hosts that respond: attempts SNMP sysName.
    - Creates Device records for IPs not already in inventory.
    """
    from .models import Device

    network_str = getattr(settings, 'MGMT_NETWORK', '192.168.100.0/24')
    try:
        network = ipaddress.ip_network(network_str, strict=False)
    except ValueError:
        logger.error('Invalid MGMT_NETWORK: %s', network_str)
        return {'error': 'invalid_network'}

    known_ips = set(Device.objects.values_list('ip_address', flat=True))
    found_new   = []
    found_up    = []

    for host in network.hosts():
        ip_str = str(host)
        alive  = _ping(ip_str)
        if not alive:
            continue

        found_up.append(ip_str)

        if ip_str in known_ips:
            # Just update the status of the existing device
            Device.objects.filter(ip_address=ip_str).update(
                status=Device.STATUS_UP,
                last_seen=timezone.now(),
                last_polled=timezone.now(),
            )
            continue

        # New device — try to learn hostname via SNMP
        hostname = (
            _snmp_get_sysname(ip_str, community='public')
            or f'device-{ip_str.replace(".", "-")}'
        )

        device = Device.objects.create(
            hostname=hostname,
            ip_address=ip_str,
            status=Device.STATUS_UP,
            last_seen=timezone.now(),
            last_polled=timezone.now(),
        )
        found_new.append({'ip': ip_str, 'hostname': device.hostname})
        logger.info('Auto-discovered: %s (%s)', device.hostname, ip_str)

    return {
        'network': network_str,
        'hosts_alive': len(found_up),
        'new_devices': len(found_new),
        'new': found_new,
    }
