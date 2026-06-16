import logging

from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Alert
from .serializers import AlertSerializer, AlertManagerWebhookSerializer, AcknowledgeSerializer

logger = logging.getLogger(__name__)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Alert.objects.select_related('acknowledged_by').order_by('-received_at')
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'severity', 'site', 'alertname', 'acknowledged']
    search_fields = ['alertname', 'instance', 'summary', 'description']
    ordering_fields = ['received_at', 'starts_at', 'severity']

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        """POST /api/monitoring/alerts/{id}/acknowledge/ — acknowledge an alert."""
        alert = self.get_object()
        if alert.acknowledged:
            return Response({'detail': 'Already acknowledged.'}, status=status.HTTP_200_OK)

        ser = AcknowledgeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        alert.acknowledged    = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.ack_note        = ser.validated_data.get('note', '')
        alert.save(update_fields=['acknowledged', 'acknowledged_by', 'acknowledged_at', 'ack_note'])

        return Response(AlertSerializer(alert).data)

    @action(detail=False, methods=['get'], url_path='active-summary')
    def active_summary(self, request):
        """GET /api/monitoring/alerts/active-summary/ — counts by severity."""
        qs = Alert.objects.filter(status='firing')
        return Response({
            'total':    qs.count(),
            'critical': qs.filter(severity='critical').count(),
            'warning':  qs.filter(severity='warning').count(),
            'info':     qs.filter(severity='info').count(),
            'unacked':  qs.filter(acknowledged=False).count(),
        })


@api_view(['POST'])
@pc([AllowAny])
def alerts_webhook(request):
    """
    POST /api/alerts/webhook/
    Receives batched alert notifications from AlertManager.
    Creates / resolves Alert records and optionally triggers Celery reconciliation.
    """
    ser = AlertManagerWebhookSerializer(data=request.data)
    if not ser.is_valid():
        logger.warning('alerts_webhook: invalid payload: %s', ser.errors)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    payload = ser.validated_data
    created_count  = 0
    resolved_count = 0

    for raw_alert in payload['alerts']:
        labels      = raw_alert.get('labels', {})
        annotations = raw_alert.get('annotations', {})
        fingerprint = raw_alert.get('fingerprint', '')
        alert_status = raw_alert.get('status', 'firing')

        if not fingerprint:
            logger.warning('alerts_webhook: alert without fingerprint, skipping')
            continue

        defaults = {
            'alertname':   labels.get('alertname', ''),
            'instance':    labels.get('instance', ''),
            'site':        labels.get('site', ''),
            'severity':    labels.get('severity', 'warning'),
            'status':      alert_status,
            'summary':     annotations.get('summary', ''),
            'description': annotations.get('description', ''),
            'raw_labels':  labels,
            'raw_payload': dict(raw_alert),
            'starts_at':   raw_alert.get('startsAt'),
            'ends_at':     raw_alert.get('endsAt') if alert_status == 'resolved' else None,
        }

        alert, created = Alert.objects.update_or_create(
            fingerprint=fingerprint,
            defaults=defaults,
        )

        if created:
            created_count += 1
            logger.info(
                'alerts_webhook: NEW [%s] %s — %s',
                labels.get('severity', '?'), labels.get('alertname', '?'),
                labels.get('instance', '?'),
            )
            # Send email for newly firing alerts
            if alert_status == 'firing':
                from .tasks import send_alert_email
                send_alert_email.apply_async(
                    (alert.pk, 'firing'), queue='monitoring', countdown=5,
                )
        elif alert_status == 'resolved':
            resolved_count += 1
            logger.info('alerts_webhook: RESOLVED %s — %s',
                        labels.get('alertname', '?'), labels.get('instance', '?'))
            # Send resolved notification
            from .tasks import send_alert_email
            send_alert_email.apply_async(
                (alert.pk, 'resolved'), queue='monitoring', countdown=5,
            )

        # Immediately update device status for DeviceDown alerts
        if labels.get('alertname') == 'DeviceDown':
            _handle_device_down(labels.get('instance', ''), alert_status)

    # Trigger async reconciliation in background
    from .tasks import mark_devices_from_alerts
    mark_devices_from_alerts.apply_async(countdown=5, queue='monitoring')

    return Response({
        'received': len(payload['alerts']),
        'created':  created_count,
        'resolved': resolved_count,
    }, status=status.HTTP_200_OK)


def _handle_device_down(ip_address: str, alert_status: str):
    """Synchronously update device status on DeviceDown/Resolved alert."""
    if not ip_address:
        return
    from apps.inventory.models import Device
    try:
        device = Device.objects.get(ip_address=ip_address)
        if alert_status == 'firing':
            Device.objects.filter(pk=device.pk).update(status='down')
        elif alert_status == 'resolved':
            # Only restore to 'unknown' — polling will set it to 'up' when it responds
            Device.objects.filter(pk=device.pk, status='down').update(status='unknown')
    except Device.DoesNotExist:
        pass
    except Exception as exc:
        logger.warning('_handle_device_down: %s', exc)
