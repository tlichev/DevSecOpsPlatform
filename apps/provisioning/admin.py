from django.contrib import admin
from .models import ConfigTemplate, ProvisioningJob, ProvisioningResult, AuditLog


@admin.register(ConfigTemplate)
class ConfigTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "template_type", "vendor", "created_at"]
    search_fields = ["name", "description"]


@admin.register(ProvisioningJob)
class ProvisioningJobAdmin(admin.ModelAdmin):
    list_display = ["id", "template", "status", "initiated_by", "created_at"]
    readonly_fields = ["celery_task_id", "rendered_config", "started_at", "completed_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "actor", "device", "success", "timestamp"]
    list_filter = ["action", "success"]
    readonly_fields = ["timestamp"]
