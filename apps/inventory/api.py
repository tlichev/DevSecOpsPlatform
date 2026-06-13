from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsEngineerOrReadOnly
from .models import Device
from .serializers import DeviceSerializer, DeviceListSerializer, DeviceStatusSerializer
from .filters import DeviceFilter
from .tasks import poll_device, poll_all_devices, discover_network


class DeviceViewSet(viewsets.ModelViewSet):
    queryset         = Device.objects.all()
    permission_classes = [IsEngineerOrReadOnly]
    filter_backends  = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class  = DeviceFilter
    search_fields    = ['hostname', 'ip_address', 'description', 'model']
    ordering_fields  = ['hostname', 'site', 'device_type', 'status', 'last_seen', 'updated_at']
    ordering         = ['site', 'hostname']

    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        if self.action == 'status_list':
            return DeviceStatusSerializer
        return DeviceSerializer

    # ── Custom actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='poll')
    def poll(self, request, pk=None):
        """Enqueue an immediate ICMP + SNMP status poll for this device."""
        device = self.get_object()
        task = poll_device.apply_async(args=[device.pk], queue='monitoring')
        return Response({
            'task_id': task.id,
            'message': f'Polling {device.hostname} ({device.ip_address})…',
        })

    @action(detail=False, methods=['post'], url_path='poll-all')
    def poll_all(self, request):
        """Enqueue status polls for every device."""
        task = poll_all_devices.apply_async(queue='monitoring')
        return Response({'task_id': task.id, 'message': 'Polling all devices…'})

    @action(detail=False, methods=['post'], url_path='discover')
    def discover(self, request):
        """Trigger auto-discovery scan of the management network."""
        task = discover_network.apply_async(queue='discovery')
        return Response({'task_id': task.id, 'message': 'Discovery scan started…'})

    @action(detail=False, methods=['get'], url_path='status')
    def status_list(self, request):
        """Lightweight status list consumed by topology.js."""
        devices = Device.objects.only(
            'id', 'hostname', 'site', 'device_type', 'status'
        )
        serializer = DeviceStatusSerializer(devices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-site/(?P<site>[a-z]+)')
    def by_site(self, request, site=None):
        """All devices for a given site."""
        qs = Device.objects.filter(site=site)
        serializer = DeviceListSerializer(qs, many=True)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Aggregate stats consumed by the dashboard page."""
    total   = Device.objects.count()
    up      = Device.objects.filter(status=Device.STATUS_UP).count()
    down    = Device.objects.filter(status=Device.STATUS_DOWN).count()
    unknown = Device.objects.filter(status=Device.STATUS_UNKNOWN).count()

    sites_online = (
        Device.objects
        .filter(status=Device.STATUS_UP)
        .values('site')
        .distinct()
        .count()
    )

    try:
        from apps.monitoring.models import Alert
        active_alerts   = Alert.objects.filter(status='firing').count()
        critical_alerts = Alert.objects.filter(status='firing', severity='critical').count()
    except Exception:
        active_alerts = critical_alerts = 0

    try:
        from django.db.models import Max
        from apps.security.models import ComplianceResult
        ids = (
            ComplianceResult.objects
            .values('device', 'rule')
            .annotate(latest=Max('id'))
            .values_list('latest', flat=True)
        )
        qs    = ComplianceResult.objects.filter(id__in=ids)
        total_c = qs.filter(status__in=['pass', 'fail']).count()
        pass_c  = qs.filter(status='pass').count()
        compliance_pct = round(pass_c / total_c * 100) if total_c else 0
    except Exception:
        compliance_pct = 0

    return Response({
        'total_devices':   total,
        'devices_up':      up,
        'devices_down':    down,
        'devices_unknown': unknown,
        'sites_online':    sites_online,
        'active_alerts':   active_alerts,
        'critical_alerts': critical_alerts,
        'compliance_pct':  compliance_pct,
    })
