import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.inventory.permissions import IsAdminOrNetworkEngineer, ReadOnlyOrAbove
from .models import ConfigTemplate, ProvisioningJob, AuditLog
from .serializers import (
    ConfigTemplateSerializer, ProvisioningJobSerializer, AuditLogSerializer
)
from .tasks import execute_provisioning_job

logger = logging.getLogger(__name__)


class ConfigTemplateViewSet(viewsets.ModelViewSet):
    queryset = ConfigTemplate.objects.all()
    serializer_class = ConfigTemplateSerializer
    permission_classes = [IsAdminOrNetworkEngineer]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """Render the template with supplied variables without pushing."""
        template = self.get_object()
        variables = request.data.get("variables", {})
        from .jinja_renderer import render_template
        try:
            rendered = render_template(template.body, variables)
            return Response({"rendered": rendered})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ProvisioningJobViewSet(viewsets.ModelViewSet):
    queryset = ProvisioningJob.objects.prefetch_related("devices", "results").select_related("template", "initiated_by")
    serializer_class = ProvisioningJobSerializer
    permission_classes = [IsAdminOrNetworkEngineer]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job = serializer.save(initiated_by=request.user)
        task = execute_provisioning_job.delay(job.id)
        job.celery_task_id = task.id
        job.save(update_fields=["celery_task_id"])

        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor", "device").order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [ReadOnlyOrAbove]
    filterset_fields = ["action", "success", "device"]
    search_fields = ["actor__username", "device__hostname"]
    ordering_fields = ["timestamp"]
