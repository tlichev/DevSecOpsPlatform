import logging

from django.shortcuts import get_object_or_404, render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Device, DiscoveryJob
from .serializers import DeviceSerializer, DeviceListSerializer, DiscoveryJobSerializer
from .permissions import ReadOnlyOrAbove, IsAdminOrNetworkEngineer
from .tasks import run_discovery, check_device_reachability

logger = logging.getLogger(__name__)


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    permission_classes = [ReadOnlyOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "device_type", "vendor", "site"]
    search_fields = ["hostname", "ip_address", "description", "site"]
    ordering_fields = ["hostname", "ip_address", "status", "created_at"]
    ordering = ["hostname"]

    def get_serializer_class(self):
        if self.action == "list":
            return DeviceListSerializer
        return DeviceSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrNetworkEngineer])
    def check_reachability(self, request, pk=None):
        device = self.get_object()
        task = check_device_reachability.delay(device.id)
        return Response({"task_id": task.id, "message": f"Reachability check started for {device.hostname}"})

    @action(detail=True, methods=["get"])
    def status_detail(self, request, pk=None):
        device = self.get_object()
        return Response({
            "id": device.id,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "status": device.status,
            "os_version": device.os_version,
        })


class DiscoveryJobViewSet(viewsets.ModelViewSet):
    queryset = DiscoveryJob.objects.select_related("initiated_by")
    serializer_class = DiscoveryJobSerializer
    permission_classes = [IsAdminOrNetworkEngineer]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subnet = serializer.validated_data["subnet"]

        job = DiscoveryJob.objects.create(
            subnet=subnet,
            initiated_by=request.user,
            status=DiscoveryJob.Status.PENDING,
        )
        task = run_discovery.delay(job.id)
        job.celery_task_id = task.id
        job.save(update_fields=["celery_task_id"])

        return Response(
            DiscoveryJobSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        job = self.get_object()
        return Response(DiscoveryJobSerializer(job).data)
