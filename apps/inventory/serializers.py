from rest_framework import serializers
from .models import Device, DiscoveryJob


class DeviceSerializer(serializers.ModelSerializer):
    netmiko_device_type = serializers.ReadOnlyField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    device_type_display = serializers.CharField(source="get_device_type_display", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id", "hostname", "ip_address", "device_type", "device_type_display",
            "vendor", "os_version", "description", "status", "status_display",
            "ssh_username", "ssh_port", "snmp_community", "snmp_version",
            "site", "rack", "tags", "discovered_at", "created_at", "updated_at",
            "netmiko_device_type",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "discovered_at", "netmiko_device_type"]
        extra_kwargs = {
            "ssh_password": {"write_only": True},
        }

    def validate_ip_address(self, value):
        import ipaddress
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise serializers.ValidationError("Invalid IP address format.")
        return value


class DeviceListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""
    class Meta:
        model = Device
        fields = ["id", "hostname", "ip_address", "device_type", "vendor", "status", "site"]


class DiscoveryJobSerializer(serializers.ModelSerializer):
    initiated_by_username = serializers.CharField(source="initiated_by.username", read_only=True)

    class Meta:
        model = DiscoveryJob
        fields = [
            "id", "subnet", "status", "started_at", "completed_at",
            "devices_found", "devices_added", "log", "initiated_by_username",
            "celery_task_id", "created_at",
        ]
        read_only_fields = [
            "id", "status", "started_at", "completed_at", "devices_found",
            "devices_added", "log", "celery_task_id", "created_at",
        ]
