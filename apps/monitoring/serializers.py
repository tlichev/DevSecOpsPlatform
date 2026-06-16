from rest_framework import serializers
from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    acknowledged_by_username = serializers.CharField(
        source='acknowledged_by.username', read_only=True, default=None
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'fingerprint', 'alertname', 'instance', 'site',
            'severity', 'status', 'is_active',
            'summary', 'description',
            'starts_at', 'ends_at', 'received_at',
            'acknowledged', 'acknowledged_by', 'acknowledged_by_username',
            'acknowledged_at', 'ack_note',
        ]
        read_only_fields = [
            'id', 'fingerprint', 'alertname', 'instance', 'site',
            'severity', 'status', 'summary', 'description',
            'starts_at', 'ends_at', 'received_at',
            'acknowledged_by', 'acknowledged_at',
        ]


# ── AlertManager webhook payload structure ────────────────────────────────────

class _NullableStrField(serializers.CharField):
    """CharField that coerces None to empty string instead of rejecting it."""
    def to_internal_value(self, data):
        if data is None:
            return ''
        return super().to_internal_value(data)


class _AlertManagerAlertSerializer(serializers.Serializer):
    status       = serializers.CharField()
    labels       = serializers.DictField(child=_NullableStrField(allow_blank=True), default=dict)
    annotations  = serializers.DictField(child=_NullableStrField(allow_blank=True), required=False, default=dict)
    startsAt     = serializers.DateTimeField(required=False, allow_null=True)
    endsAt       = serializers.DateTimeField(required=False, allow_null=True)
    fingerprint  = serializers.CharField(max_length=64)
    generatorURL = serializers.CharField(required=False, allow_blank=True, default='')


class AlertManagerWebhookSerializer(serializers.Serializer):
    version           = serializers.CharField(default='4')
    groupKey          = serializers.CharField(required=False, allow_blank=True, default='')
    status            = serializers.CharField()
    receiver          = serializers.CharField(required=False, allow_blank=True, default='')
    groupLabels       = serializers.DictField(child=_NullableStrField(allow_blank=True), default=dict)
    commonLabels      = serializers.DictField(child=_NullableStrField(allow_blank=True), default=dict)
    commonAnnotations = serializers.DictField(child=_NullableStrField(allow_blank=True), default=dict)
    externalURL       = serializers.CharField(required=False, allow_blank=True, default='')
    alerts            = _AlertManagerAlertSerializer(many=True)


class AcknowledgeSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default='')
