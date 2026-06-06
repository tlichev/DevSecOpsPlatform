from django.contrib import admin
from .models import Alert, GrafanaDashboard


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["alert_name", "severity", "status", "instance", "device", "received_at", "acknowledged"]
    list_filter = ["severity", "status", "acknowledged"]
    search_fields = ["alert_name", "instance"]
    readonly_fields = ["received_at", "fingerprint"]


@admin.register(GrafanaDashboard)
class GrafanaDashboardAdmin(admin.ModelAdmin):
    list_display = ["title", "uid", "order"]
