from django.db import models
from apps.inventory.models import Device


class AlertSeverity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    WARNING = "warning", "Warning"
    INFO = "info", "Info"
    RESOLVED = "resolved", "Resolved"


class Alert(models.Model):
    """Alert ingested from Prometheus AlertManager webhook."""
    alert_name = models.CharField(max_length=255)
    severity = models.CharField(max_length=16, choices=AlertSeverity.choices, default=AlertSeverity.INFO)
    status = models.CharField(max_length=16, default="firing")  # firing | resolved
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    instance = models.CharField(max_length=255, blank=True)
    labels = models.JSONField(default=dict)
    annotations = models.JSONField(default=dict)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    generator_url = models.URLField(blank=True)
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["status", "severity"]),
            models.Index(fields=["alert_name"]),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.alert_name} on {self.instance}"


class GrafanaDashboard(models.Model):
    """Reference to a Grafana dashboard embedded in the UI."""
    title = models.CharField(max_length=255)
    uid = models.CharField(max_length=64, unique=True)
    panel_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    embed_url = models.CharField(max_length=512, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title
