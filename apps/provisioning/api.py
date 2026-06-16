import logging

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import ProvisioningTemplate, AuditLog
from .serializers import (
    ProvisioningTemplateSerializer,
    ProvisioningTemplateListSerializer,
    AuditLogSerializer,
    RenderPreviewSerializer,
    PushConfigSerializer,
)
from .template_engine import list_all_templates, render_template
from .tasks import push_config_to_devices, pull_running_config

logger = logging.getLogger(__name__)


class IsEngineerOrReadOnly(permissions.BasePermission):
    """Engineers can write; read-only users can only GET."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_engineer() or request.user.is_superuser
        )


class ProvisioningTemplateViewSet(viewsets.ModelViewSet):
    queryset = ProvisioningTemplate.objects.select_related('created_by').order_by('-updated_at')
    permission_classes = [IsEngineerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device_type', 'site', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'updated_at', 'device_type']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProvisioningTemplateListSerializer
        return ProvisioningTemplateSerializer

    @action(detail=False, methods=['get'], url_path='all-names')
    def all_names(self, request):
        """Return combined list of DB + file templates for the dropdown."""
        templates = list_all_templates()
        return Response(templates)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        AuditLog.objects
        .select_related('device', 'user')
        .order_by('-timestamp')
    )
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device__site', 'device']
    search_fields = ['device__hostname', 'template_name', 'action', 'user__username']
    ordering_fields = ['timestamp', 'execution_time', 'status']


# ── Functional API views ───────────────────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated


@api_view(['POST'])
@pc([IsAuthenticated])
def render_preview_view(request):
    """POST /api/provisioning/render/ — render a template for a single device."""
    ser = RenderPreviewSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    d = ser.validated_data
    try:
        from apps.inventory.models import Device
        device = Device.objects.get(pk=d['device_id'])
        rendered = render_template(d['template_name'], device, d.get('extra_context', {}))
        return Response({
            'rendered':  rendered,
            'device':    device.hostname,
            'template':  d['template_name'],
        })
    except Exception as exc:
        logger.warning('render_preview error: %s', exc)
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@pc([IsAuthenticated])
def push_config_view(request):
    """POST /api/provisioning/push/ — dispatch Celery push task(s)."""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response(
            {'error': 'Engineer role required to push configs.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    ser = PushConfigSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    d = ser.validated_data
    result = push_config_to_devices.delay(
        d['device_ids'],
        d['template_name'],
        d.get('extra_context', {}),
        request.user.pk,
        d.get('dry_run', False),
    )
    return Response({
        'task_id':      result.id,
        'device_count': len(d['device_ids']),
        'template':     d['template_name'],
        'dry_run':      d.get('dry_run', False),
        'status':       'queued',
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@pc([IsAuthenticated])
def pull_config_trigger_view(request):
    """POST /api/provisioning/pull-config/ — queue a running-config pull for one device."""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response({'error': 'Engineer role required.'}, status=status.HTTP_403_FORBIDDEN)

    device_id = request.data.get('device_id')
    if not device_id:
        return Response({'error': 'device_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from apps.inventory.models import Device
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return Response({'error': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)

    result = pull_running_config.apply_async((device_id, request.user.pk), queue='provisioning')
    return Response({
        'task_id': result.id,
        'device':  device.hostname,
        'status':  'queued',
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@pc([IsAuthenticated])
def task_status_view(request, task_id: str):
    """GET /api/provisioning/task/<task_id>/ — poll Celery task result."""
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    data = {'task_id': task_id, 'state': result.state}
    if result.ready():
        data['result'] = result.result if not isinstance(result.result, Exception) else str(result.result)
    return Response(data)
