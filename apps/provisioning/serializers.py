from rest_framework import serializers
from .models import ConfigTemplate, ProvisioningJob, ProvisioningResult, AuditLog


class ConfigTemplateSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ConfigTemplate
        fields = [
            "id", "name", "template_type", "description", "body",
            "variables_schema", "vendor", "created_by_username", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProvisioningResultSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)
    device_ip = serializers.CharField(source="device.ip_address", read_only=True)

    class Meta:
        model = ProvisioningResult
        fields = ["id", "device_hostname", "device_ip", "success", "output", "error", "duration_seconds", "executed_at"]


class ProvisioningJobSerializer(serializers.ModelSerializer):
    results = ProvisioningResultSerializer(many=True, read_only=True)
    initiated_by_username = serializers.CharField(source="initiated_by.username", read_only=True)
    device_ids = serializers.PrimaryKeyRelatedField(
        many=True, source="devices", queryset=__import__("apps.inventory.models", fromlist=["Device"]).Device.objects.all()
    )

    class Meta:
        model = ProvisioningJob
        fields = [
            "id", "template", "device_ids", "variables", "rendered_config",
            "status", "initiated_by_username", "celery_task_id",
            "started_at", "completed_at", "created_at", "results",
        ]
        read_only_fields = [
            "id", "rendered_config", "status", "celery_task_id",
            "started_at", "completed_at", "created_at", "results",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    device_hostname = serializers.CharField(source="device.hostname", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "actor_username", "device_hostname",
            "detail", "success", "ip_address", "timestamp",
        ]
