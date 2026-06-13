from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog, ProvisioningTemplate


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'device_link', 'user', 'template_name',
                     'status_badge', 'duration_display', 'task_id_short')
    list_filter   = ('status', 'device__site', 'device__device_type')
    search_fields = ('device__hostname', 'template_name', 'action', 'task_id')
    ordering      = ('-timestamp',)
    readonly_fields = ('timestamp', 'task_id', 'execution_time',
                       'config_sent', 'config_diff', 'error_message')
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Summary', {
            'fields': ('timestamp', 'user', 'device', 'action',
                       'template_name', 'status', 'error_message'),
        }),
        ('Task', {
            'fields': ('task_id', 'execution_time'),
        }),
        ('Config', {
            'fields': ('config_sent', 'config_diff'),
            'classes': ('collapse',),
        }),
    )

    def device_link(self, obj):
        return format_html(
            '<a href="/admin/inventory/device/{}/change/">{}</a>',
            obj.device_id, obj.device.hostname
        )
    device_link.short_description = 'Device'

    def status_badge(self, obj):
        colors = {'success': '#10b981', 'failed': '#ef4444', 'pending': '#f59e0b'}
        c = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:700">● {}</span>', c, obj.status.title()
        )
    status_badge.short_description = 'Status'

    def task_id_short(self, obj):
        return obj.task_id[:8] + '…' if obj.task_id else '—'
    task_id_short.short_description = 'Task'


@admin.register(ProvisioningTemplate)
class ProvisioningTemplateAdmin(admin.ModelAdmin):
    list_display  = ('name', 'device_type', 'site', 'is_active', 'updated_at')
    list_filter   = ('is_active', 'device_type', 'site')
    search_fields = ('name', 'description', 'content')
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
