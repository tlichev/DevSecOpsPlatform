from django.contrib import admin
from django.utils.html import format_html
from .models import ComplianceRule, ComplianceResult, GoldenConfig, DriftResult


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'severity_badge', 'match_means_pass',
                     'is_active', 'updated_at')
    list_filter   = ('is_active', 'severity', 'category')
    search_fields = ('name', 'description', 'pattern', 'category')
    ordering      = ('category', 'name')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'description', 'category', 'severity', 'is_active'),
        }),
        ('Check Logic', {
            'fields': ('pattern', 'match_means_pass', 'device_types'),
            'description': 'The pattern is a Python regex applied to the full running-config.',
        }),
        ('Remediation', {
            'fields': ('remediation',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def severity_badge(self, obj):
        colors = {'critical': '#ef4444', 'warning': '#f59e0b', 'info': '#3b82f6'}
        c = colors.get(obj.severity, '#6b7280')
        return format_html('<span style="color:{};font-weight:700">● {}</span>', c, obj.severity.upper())
    severity_badge.short_description = 'Severity'


@admin.register(ComplianceResult)
class ComplianceResultAdmin(admin.ModelAdmin):
    list_display  = ('checked_at', 'device_link', 'rule_link', 'status_badge', 'task_id_short')
    list_filter   = ('status', 'rule__category', 'rule__severity', 'device__site')
    search_fields = ('device__hostname', 'rule__name', 'evidence')
    ordering      = ('-checked_at',)
    readonly_fields = ('checked_at', 'task_id', 'evidence', 'error_message')
    date_hierarchy = 'checked_at'

    def device_link(self, obj):
        return format_html(
            '<a href="/admin/inventory/device/{}/change/">{}</a>',
            obj.device_id, obj.device.hostname
        )
    device_link.short_description = 'Device'

    def rule_link(self, obj):
        return format_html(
            '<a href="/admin/security/compliancerule/{}/change/">{}</a>',
            obj.rule_id, obj.rule.name
        )
    rule_link.short_description = 'Rule'

    def status_badge(self, obj):
        colors = {'pass': '#10b981', 'fail': '#ef4444', 'error': '#f59e0b', 'skipped': '#6b7280'}
        c = colors.get(obj.status, '#6b7280')
        return format_html('<span style="color:{};font-weight:700">● {}</span>', c, obj.status.title())
    status_badge.short_description = 'Status'

    def task_id_short(self, obj):
        return obj.task_id[:8] + '…' if obj.task_id else '—'
    task_id_short.short_description = 'Task'


@admin.register(GoldenConfig)
class GoldenConfigAdmin(admin.ModelAdmin):
    list_display  = ('device_type', 'name', 'version', 'is_active', 'updated_at')
    list_filter   = ('is_active', 'device_type')
    search_fields = ('name', 'description', 'device_type')
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DriftResult)
class DriftResultAdmin(admin.ModelAdmin):
    list_display  = ('checked_at', 'device_link', 'status_badge', 'drift_lines', 'task_id_short')
    list_filter   = ('status', 'device__site')
    search_fields = ('device__hostname',)
    ordering      = ('-checked_at',)
    readonly_fields = ('checked_at', 'task_id', 'diff', 'running_config', 'error_message', 'drift_lines')
    date_hierarchy = 'checked_at'

    fieldsets = (
        ('Summary', {
            'fields': ('device', 'golden_config', 'status', 'drift_lines', 'task_id', 'checked_at'),
        }),
        ('Error', {
            'fields': ('error_message',),
            'classes': ('collapse',),
        }),
        ('Diff', {
            'fields': ('diff',),
            'classes': ('collapse',),
        }),
        ('Running Config Snapshot', {
            'fields': ('running_config',),
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
        colors = {'clean': '#10b981', 'drifted': '#f59e0b', 'error': '#ef4444'}
        c = colors.get(obj.status, '#6b7280')
        return format_html('<span style="color:{};font-weight:700">● {}</span>', c, obj.status.title())
    status_badge.short_description = 'Status'

    def task_id_short(self, obj):
        return obj.task_id[:8] + '…' if obj.task_id else '—'
    task_id_short.short_description = 'Task'
