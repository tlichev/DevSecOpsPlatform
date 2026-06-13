from django.contrib import admin
from django.utils.html import format_html
from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display  = ('hostname', 'ip_address', 'site_badge', 'type_badge',
                     'vendor', 'status_badge', 'last_seen', 'updated_at')
    list_filter   = ('site', 'device_type', 'status', 'vendor')
    search_fields = ('hostname', 'ip_address', 'description', 'model')
    ordering      = ('site', 'hostname')
    readonly_fields = ('created_at', 'updated_at', 'last_seen', 'last_polled')

    fieldsets = (
        ('Identity', {
            'fields': ('hostname', 'ip_address', 'wan_ip', 'loopback_ip', 'description'),
        }),
        ('Classification', {
            'fields': ('site', 'device_type', 'vendor', 'model', 'os_version'),
        }),
        ('Status', {
            'fields': ('status', 'last_seen', 'last_polled'),
        }),
        ('SNMP', {
            'fields': ('snmp_community', 'snmp_version'),
        }),
        ('SSH Credentials', {
            'fields': ('ssh_username', 'ssh_password'),
            'classes': ('collapse',),
            'description': 'Password is stored encrypted at rest.',
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        raw_pw = form.cleaned_data.get('ssh_password', '')
        if raw_pw and not raw_pw.startswith('gAAAAA'):
            obj.set_encrypted_password(raw_pw)
        super().save_model(request, obj, form, change)

    def site_badge(self, obj):
        colors = {
            'sofia': '#10b981', 'burgas': '#3b82f6',
            'plovdiv': '#a855f7', 'wan': '#f59e0b',
        }
        c = colors.get(obj.site, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600">{}</span>',
            c, obj.get_site_display()
        )
    site_badge.short_description = 'Site'

    def type_badge(self, obj):
        return format_html(
            '<span style="font-size:12px;color:#9ca3af">{}</span>',
            obj.get_device_type_display()
        )
    type_badge.short_description = 'Type'

    def status_badge(self, obj):
        colors = {'up': '#10b981', 'down': '#ef4444', 'unknown': '#6b7280'}
        c = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:700">● {}</span>',
            c, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
