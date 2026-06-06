from rest_framework import serializers
from .models import Alert, GrafanaDashboard


class AlertSerializer(serializers.ModelSerializer):
    device_hostname = serializers.CharField(source="device.hostname", read_only=True, allow_null=True)

    class Meta:
        model = Alert
        fields = [
            "id", "alert_name", "severity", "status", "device_hostname",
            "instance", "labels", "annotations", "starts_at", "ends_at",
            "fingerprint", "received_at", "acknowledged", "acknowledged_at",
        ]


class GrafanaDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrafanaDashboard
        fields = ["id", "title", "uid", "panel_id", "description", "embed_url", "order"]


class AlertManagerWebhookSerializer(serializers.Serializer):
    """Deserializes the AlertManager webhook payload."""
    version = serializers.CharField()
    groupKey = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    receiver = serializers.CharField()
    groupLabels = serializers.DictField(child=serializers.CharField())
    commonLabels = serializers.DictField(child=serializers.CharField())
    commonAnnotations = serializers.DictField(child=serializers.CharField())
    externalURL = serializers.CharField(required=False, allow_blank=True)
    alerts = serializers.ListField(child=serializers.DictField())
