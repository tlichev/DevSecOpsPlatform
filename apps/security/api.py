import logging

from django.db.models import Count, Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import ComplianceRule, ComplianceResult, GoldenConfig, DriftResult
from .serializers import (
    ComplianceRuleSerializer,
    ComplianceResultSerializer,
    GoldenConfigSerializer,
    DriftResultSerializer,
)
from .tasks import (
    run_compliance_checks,
    run_all_compliance_checks,
    check_golden_config_drift,
    run_all_drift_checks,
)

logger = logging.getLogger(__name__)


class IsEngineerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_engineer() or request.user.is_superuser
        )


# ── ViewSets ───────────────────────────────────────────────────────────────────

class ComplianceRuleViewSet(viewsets.ModelViewSet):
    queryset = ComplianceRule.objects.all()
    serializer_class = ComplianceRuleSerializer
    permission_classes = [IsEngineerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'severity', 'category']
    search_fields = ['name', 'description', 'category']
    ordering_fields = ['name', 'category', 'severity', 'updated_at']


class ComplianceResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        ComplianceResult.objects
        .select_related('device', 'rule')
        .order_by('-checked_at')
    )
    serializer_class = ComplianceResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device', 'rule', 'rule__category', 'device__site']
    search_fields = ['device__hostname', 'rule__name', 'rule__category']
    ordering_fields = ['checked_at', 'status']


class GoldenConfigViewSet(viewsets.ModelViewSet):
    queryset = GoldenConfig.objects.select_related('created_by').all()
    serializer_class = GoldenConfigSerializer
    permission_classes = [IsEngineerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['device_type', 'is_active']
    search_fields = ['name', 'description', 'device_type']


class DriftResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        DriftResult.objects
        .select_related('device', 'golden_config')
        .order_by('-checked_at')
    )
    serializer_class = DriftResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device', 'device__site']
    search_fields = ['device__hostname']
    ordering_fields = ['checked_at', 'drift_lines', 'status']


# ── Functional views ───────────────────────────────────────────────────────────

@api_view(['POST'])
@pc([IsAuthenticated])
def run_compliance_view(request, device_id: int):
    """POST /api/security/compliance/run/<device_id>/"""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response({'error': 'Engineer role required.'}, status=403)
    task = run_compliance_checks.apply_async(args=[device_id], queue='default')
    return Response({'task_id': task.id, 'device_id': device_id}, status=202)


@api_view(['POST'])
@pc([IsAuthenticated])
def run_all_compliance_view(request):
    """POST /api/security/compliance/run-all/"""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response({'error': 'Engineer role required.'}, status=403)
    task = run_all_compliance_checks.apply_async(queue='default')
    return Response({'task_id': task.id}, status=202)


@api_view(['POST'])
@pc([IsAuthenticated])
def run_drift_view(request, device_id: int):
    """POST /api/security/drift/run/<device_id>/"""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response({'error': 'Engineer role required.'}, status=403)
    task = check_golden_config_drift.apply_async(args=[device_id], queue='default')
    return Response({'task_id': task.id, 'device_id': device_id}, status=202)


@api_view(['POST'])
@pc([IsAuthenticated])
def run_all_drift_view(request):
    """POST /api/security/drift/run-all/"""
    if not (request.user.is_engineer() or request.user.is_superuser):
        return Response({'error': 'Engineer role required.'}, status=403)
    task = run_all_drift_checks.apply_async(queue='default')
    return Response({'task_id': task.id}, status=202)


@api_view(['GET'])
@pc([IsAuthenticated])
def compliance_summary_view(request):
    """GET /api/security/compliance/summary/ — aggregate stats for dashboard."""
    from django.db.models import Max

    # Only use latest result per device+rule pair
    latest_ids = (
        ComplianceResult.objects
        .values('device', 'rule')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    qs = ComplianceResult.objects.filter(id__in=latest_ids)

    total   = qs.count()
    passing = qs.filter(status='pass').count()
    failing = qs.filter(status='fail').count()
    errored = qs.filter(status='error').count()

    # Per-device score
    from apps.inventory.models import Device
    device_ids_checked = qs.values_list('device', flat=True).distinct()
    devices_compliant  = 0
    for did in device_ids_checked:
        dq  = qs.filter(device_id=did)
        dp  = dq.filter(status='pass').count()
        dt  = dq.filter(status__in=['pass', 'fail']).count()
        if dt > 0 and round(dp / dt * 100) >= 80:
            devices_compliant += 1

    # Drifted devices (latest drift result per device is 'drifted')
    latest_drift_ids = (
        DriftResult.objects
        .values('device')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    devices_drifted = DriftResult.objects.filter(
        id__in=latest_drift_ids, status='drifted'
    ).count()

    last_checked = qs.aggregate(last=Max('checked_at'))['last']
    overall_score = round(passing / total * 100) if total > 0 else 0

    return Response({
        'overall_score':     overall_score,
        'total_checks':      total,
        'total_pass':        passing,
        'total_fail':        failing,
        'total_error':       errored,
        'devices_checked':   device_ids_checked.count(),
        'devices_compliant': devices_compliant,
        'devices_drifted':   devices_drifted,
        'last_checked':      last_checked,
    })
