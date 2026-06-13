from rest_framework import serializers
from .models import Device


class DeviceListSerializer(serializers.ModelSerializer):
    site_display        = serializers.CharField(source='get_site_display',        read_only=True)
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    status_display      = serializers.CharField(source='get_status_display',      read_only=True)
    site_color          = serializers.CharField(read_only=True)
    device_type_icon    = serializers.CharField(read_only=True)

    class Meta:
        model  = Device
        fields = [
            'id', 'hostname', 'ip_address',
            'site', 'site_display', 'site_color',
            'device_type', 'device_type_display', 'device_type_icon',
            'vendor', 'os_version',
            'status', 'status_display',
            'last_seen', 'updated_at',
        ]


class DeviceSerializer(serializers.ModelSerializer):
    site_display        = serializers.CharField(source='get_site_display',        read_only=True)
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    status_display      = serializers.CharField(source='get_status_display',      read_only=True)
    site_color          = serializers.CharField(read_only=True)
    role_short          = serializers.CharField(read_only=True)

    # Write-only; never echoed back in responses.
    ssh_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'},
        label='SSH Password (plaintext — stored encrypted)',
    )

    class Meta:
        model  = Device
        fields = [
            'id', 'hostname', 'ip_address', 'wan_ip', 'loopback_ip',
            'site', 'site_display', 'site_color',
            'device_type', 'device_type_display',
            'vendor', 'model', 'os_version', 'description',
            'status', 'status_display', 'role_short',
            'snmp_community', 'snmp_version',
            'ssh_username', 'ssh_password',
            'last_seen', 'last_polled',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'last_seen', 'last_polled',
            'created_at', 'updated_at',
        ]

    def create(self, validated_data):
        raw_pw = validated_data.pop('ssh_password', '')
        device = Device(**validated_data)
        if raw_pw:
            device.set_encrypted_password(raw_pw)
        device.save()
        return device

    def update(self, instance, validated_data):
        raw_pw = validated_data.pop('ssh_password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if raw_pw is not None:
            instance.set_encrypted_password(raw_pw)
        instance.save()
        return instance


class DeviceStatusSerializer(serializers.ModelSerializer):
    """Minimal serializer for the topology.js status endpoint."""
    role_short = serializers.CharField(read_only=True)

    class Meta:
        model  = Device
        fields = ['id', 'hostname', 'site', 'device_type', 'role_short', 'status']
