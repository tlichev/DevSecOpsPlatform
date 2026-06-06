from django.contrib import admin
from .models import Device, DiscoveryJob


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["hostname", "ip_address", "device_type", "vendor", "status", "site"]
    list_filter = ["status", "device_type", "vendor"]
    search_fields = ["hostname", "ip_address", "site"]
    readonly_fields = ["created_at", "updated_at", "discovered_at"]


@admin.register(DiscoveryJob)
class DiscoveryJobAdmin(admin.ModelAdmin):
    list_display = ["subnet", "status", "devices_found", "devices_added", "created_at"]
    readonly_fields = ["started_at", "completed_at", "celery_task_id", "created_at"]
