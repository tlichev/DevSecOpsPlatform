import logging
from datetime import datetime, timezone

from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.inventory.models import Device
from apps.inventory.permissions import ReadOnlyOrAbove
from .models import Alert, GrafanaDashboard, AlertSeverity
from .serializers import AlertSerializer, GrafanaDashboardSerializer, AlertManagerWebhookSerializer

logger = logging.getLogger(__name__)


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.select_related("device").order_by("-received_at")
    serializer_class = AlertSerializer
    permission_classes = [ReadOnlyOrAbove]
    filterset_fields = ["severity", "status", "acknowledged"]
    search_fields = ["alert_name", "instance"]
    http_method_names = ["get", "patch", "head", "options"]

    @action(detail=True, methods=["patch"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(tz=timezone.utc)
        alert.save(update_fields=["acknowledged", "acknowledged_at"])
        return Response(AlertSerializer(alert).data)


class GrafanaDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GrafanaDashboard.objects.all()
    serializer_class = GrafanaDashboardSerializer
    permission_classes = [IsAuthenticated]


@api_view(["POST"])
@perm_classes([AllowAny])
def alertmanager_webhook(request):
    """
    Receives alert payloads from Prometheus AlertManager.
    Endpoint: POST /api/monitoring/webhook/alertmanager/
    """
    serializer = AlertManagerWebhookSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("Invalid AlertManager payload: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    created_count = 0

    for raw_alert in data.get("alerts", []):
        labels = raw_alert.get("labels", {})
        annotations = raw_alert.get("annotations", {})
        fingerprint = raw_alert.get("fingerprint", "")
        alert_status = raw_alert.get("status", "firing")
        instance = labels.get("instance", "")
        alert_name = labels.get("alertname", "Unknown")
        severity_raw = labels.get("severity", "info").lower()
        severity = severity_raw if severity_raw in AlertSeverity.values else AlertSeverity.INFO

        # Try to match device by IP from instance label (format: ip:port)
        ip = instance.split(":")[0] if ":" in instance else instance
        device = Device.objects.filter(ip_address=ip).first()

        starts_at_str = raw_alert.get("startsAt")
        ends_at_str = raw_alert.get("endsAt")
        starts_at = parse_datetime(starts_at_str) if starts_at_str else None
        ends_at = parse_datetime(ends_at_str) if ends_at_str else None

        # Update existing or create new
        alert, created = Alert.objects.update_or_create(
            fingerprint=fingerprint,
            defaults={
                "alert_name": alert_name,
                "severity": severity,
                "status": alert_status,
                "device": device,
                "instance": instance,
                "labels": labels,
                "annotations": annotations,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "generator_url": raw_alert.get("generatorURL", ""),
            },
        )
        if created:
            created_count += 1

        logger.info("Alert %s [%s] from %s — device: %s", alert_name, alert_status, instance, device)

    return Response({"received": len(data.get("alerts", [])), "created": created_count})
