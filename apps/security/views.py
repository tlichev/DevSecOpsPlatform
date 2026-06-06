import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.inventory.permissions import IsAdminOrNetworkEngineer, ReadOnlyOrAbove, IsAdminOnly
from .models import ComplianceRule, ComplianceCheck, ConfigSnapshot, DriftReport, UserProfile
from .serializers import (
    ComplianceRuleSerializer, ComplianceCheckSerializer,
    ConfigSnapshotSerializer, DriftReportSerializer, UserProfileSerializer,
)
from .tasks import run_compliance_check, run_drift_detection, take_config_snapshot

logger = logging.getLogger(__name__)


class ComplianceRuleViewSet(viewsets.ModelViewSet):
    queryset = ComplianceRule.objects.all()
    serializer_class = ComplianceRuleSerializer
    permission_classes = [IsAdminOrNetworkEngineer]


class ComplianceCheckViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ComplianceCheck.objects.select_related("device", "rule", "initiated_by").order_by("-checked_at")
    serializer_class = ComplianceCheckSerializer
    permission_classes = [ReadOnlyOrAbove]
    filterset_fields = ["device", "rule", "status"]


class ConfigSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ConfigSnapshot.objects.select_related("device", "taken_by").order_by("-taken_at")
    serializer_class = ConfigSnapshotSerializer
    permission_classes = [ReadOnlyOrAbove]
    filterset_fields = ["device", "is_golden"]

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrNetworkEngineer])
    def set_golden(self, request, pk=None):
        snap = self.get_object()
        # Unset current golden for this device
        ConfigSnapshot.objects.filter(device=snap.device, is_golden=True).update(is_golden=False)
        snap.is_golden = True
        snap.save(update_fields=["is_golden"])
        return Response({"detail": f"Snapshot {snap.pk} is now the golden config for {snap.device.hostname}"})


class DriftReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DriftReport.objects.select_related("device").order_by("-checked_at")
    serializer_class = DriftReportSerializer
    permission_classes = [ReadOnlyOrAbove]
    filterset_fields = ["device", "status"]


class SecurityActionViewSet(viewsets.ViewSet):
    """Fire-and-forget actions that dispatch Celery tasks."""
    permission_classes = [IsAdminOrNetworkEngineer]

    @action(detail=False, methods=["post"], url_path="compliance/run")
    def run_compliance(self, request):
        device_id = request.data.get("device_id")
        rule_ids = request.data.get("rule_ids", None)
        if not device_id:
            return Response({"error": "device_id required"}, status=status.HTTP_400_BAD_REQUEST)
        task = run_compliance_check.delay(device_id, rule_ids, request.user.id)
        return Response({"task_id": task.id})

    @action(detail=False, methods=["post"], url_path="drift/run")
    def run_drift(self, request):
        device_id = request.data.get("device_id")
        if not device_id:
            return Response({"error": "device_id required"}, status=status.HTTP_400_BAD_REQUEST)
        task = run_drift_detection.delay(device_id, request.user.id)
        return Response({"task_id": task.id})

    @action(detail=False, methods=["post"], url_path="snapshot/take")
    def take_snapshot(self, request):
        device_id = request.data.get("device_id")
        set_golden = request.data.get("set_golden", False)
        if not device_id:
            return Response({"error": "device_id required"}, status=status.HTTP_400_BAD_REQUEST)
        task = take_config_snapshot.delay(device_id, set_golden, request.user.id)
        return Response({"task_id": task.id})


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related("user").all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAdminOnly]
