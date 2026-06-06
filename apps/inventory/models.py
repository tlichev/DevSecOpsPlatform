from django.db import models
from django.contrib.auth.models import User


class DeviceType(models.TextChoices):
    ROUTER = "router", "Router"
    SWITCH = "switch", "Switch"
    FIREWALL = "firewall", "Firewall"
    SERVER = "server", "Server"
    UNKNOWN = "unknown", "Unknown"


class Vendor(models.TextChoices):
    CISCO = "cisco", "Cisco"
    JUNIPER = "juniper", "Juniper"
    ARISTA = "arista", "Arista"
    PALO_ALTO = "paloalto", "Palo Alto"
    PFSENSE = "pfsense", "pfSense"
    OTHER = "other", "Other"


class DeviceStatus(models.TextChoices):
    ONLINE = "online", "Online"
    OFFLINE = "offline", "Offline"
    UNKNOWN = "unknown", "Unknown"
    MAINTENANCE = "maintenance", "Maintenance"


class Device(models.Model):
    hostname = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(unique=True)
    device_type = models.CharField(max_length=32, choices=DeviceType.choices, default=DeviceType.UNKNOWN)
    vendor = models.CharField(max_length=32, choices=Vendor.choices, default=Vendor.CISCO)
    os_version = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=DeviceStatus.choices, default=DeviceStatus.UNKNOWN)
    # SSH credentials (stored encrypted in production via django-encrypted-model-fields or vault)
    ssh_username = models.CharField(max_length=64, default="admin")
    ssh_password = models.CharField(max_length=128, blank=True)
    ssh_port = models.PositiveIntegerField(default=22)
    # SNMP
    snmp_community = models.CharField(max_length=64, default="public")
    snmp_version = models.CharField(max_length=4, default="2c")
    # Metadata
    site = models.CharField(max_length=128, blank=True)
    rack = models.CharField(max_length=64, blank=True)
    tags = models.JSONField(default=list, blank=True)
    discovered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="devices_created"
    )

    class Meta:
        ordering = ["hostname"]
        indexes = [
            models.Index(fields=["ip_address"]),
            models.Index(fields=["status"]),
            models.Index(fields=["device_type"]),
        ]

    def __str__(self):
        return f"{self.hostname} ({self.ip_address})"

    @property
    def netmiko_device_type(self):
        mapping = {
            "cisco": {"router": "cisco_ios", "switch": "cisco_ios", "firewall": "cisco_asa"},
            "juniper": {"router": "juniper_junos", "switch": "juniper_junos"},
            "arista": {"switch": "arista_eos"},
            "pfsense": {"firewall": "generic"},
        }
        return mapping.get(self.vendor, {}).get(self.device_type, "cisco_ios")


class DiscoveryJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    subnet = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    devices_found = models.PositiveIntegerField(default=0)
    devices_added = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)
    initiated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    celery_task_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Discovery {self.subnet} [{self.status}]"
