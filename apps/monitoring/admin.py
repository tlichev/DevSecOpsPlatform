from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        'received_at', 'severity_badge', 'alertname', 'instance',
        'site', 'status_badge', 'acknowledged',
    )
    list_filter  = ('status', 'severity', 'site', 'acknowledged', 'alertname')
    search_fields = ('alertname', 'instance', 'summary', 'fingerprint')
    ordering     = ('-received_at',)
    readonly_fields = (
        'fingerprint', 'received_at', 'starts_at', 'ends_at',
        'raw_labels', 'raw_payload', 'acknowledged_at', 'acknowledged_by',
    )
    date_hierarchy = 'received_at'
    actions = ['acknowledge_selected', 'resolve_selected']

    fieldsets = (
        ('Alert', {
            'fields': ('alertname', 'instance', 'site', 'severity', 'status'),
        }),
        ('Content', {
            'fields': ('summary', 'description'),
        }),
        ('Timestamps', {
            'fields': ('starts_at', 'ends_at', 'received_at'),
        }),
        ('Acknowledgement', {
            'fields': ('acknowledged', 'acknowledged_by', 'acknowledged_at', 'ack_note'),
        }),
        ('Raw Data', {
            'fields': ('fingerprint', 'raw_labels', 'raw_payload'),
            'classes': ('collapse',),
        }),
    )

    def severity_badge(self, obj):
        colors = {
            'critical': '#ef4444',
            'warning':  '#f59e0b',
            'info':     '#3b82f6',
        }
        c = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:700">● {}</span>', c, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'

    def status_badge(self, obj):
        c = '#10b981' if obj.status == 'resolved' else '#ef4444'
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', c, obj.status.title()
        )
    status_badge.short_description = 'Status'

    @admin.action(description='Acknowledge selected alerts')
    def acknowledge_selected(self, request, queryset):
        queryset.filter(acknowledged=False).update(
            acknowledged=True,
            acknowledged_by=request.user,
            acknowledged_at=timezone.now(),
        )

    @admin.action(description='Mark selected alerts as resolved')
    def resolve_selected(self, request, queryset):
        for alert in queryset.filter(status='firing'):
            alert.resolve()
