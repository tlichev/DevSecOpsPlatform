from rest_framework import serializers
from .models import ProvisioningTemplate, AuditLog


class ProvisioningTemplateSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True
    )

    class Meta:
        model = ProvisioningTemplate
        fields = [
            'id', 'name', 'description', 'device_type', 'site',
            'content', 'is_active', 'created_by', 'created_by_username',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ProvisioningTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for template dropdowns."""
    class Meta:
        model = ProvisioningTemplate
        fields = ['id', 'name', 'description', 'device_type', 'site', 'is_active']


class AuditLogSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    device_ip = serializers.CharField(source='device.management_ip', read_only=True)
    device_site = serializers.CharField(source='device.site', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='system')
    duration_display = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'device', 'device_hostname', 'device_ip', 'device_site',
            'user', 'username',
            'template_name', 'action', 'status', 'success',
            'config_sent', 'config_diff', 'error_message',
            'execution_time', 'duration_display',
            'task_id', 'timestamp',
        ]
        read_only_fields = fields


class RenderPreviewSerializer(serializers.Serializer):
    device_id = serializers.IntegerField()
    template_name = serializers.CharField(max_length=200)
    extra_context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )


class PushConfigSerializer(serializers.Serializer):
    device_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )
    template_name = serializers.CharField(max_length=200)
    extra_context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )
    dry_run = serializers.BooleanField(default=False)
