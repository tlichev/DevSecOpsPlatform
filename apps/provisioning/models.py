from django.db import models
from django.contrib.auth.models import User
from apps.inventory.models import Device


class ConfigTemplate(models.Model):
    class TemplateType(models.TextChoices):
        VLAN = "vlan", "VLAN Configuration"
        INTERFACE = "interface", "Interface Configuration"
        ACL = "acl", "Access Control List"
        ROUTING = "routing", "Routing Configuration"
        HARDENING = "hardening", "Security Hardening Baseline"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=255, unique=True)
    template_type = models.CharField(max_length=32, choices=TemplateType.choices, default=TemplateType.CUSTOM)
    description = models.TextField(blank=True)
    # Jinja2 template body
    body = models.TextField()
    # JSON schema for variables the template accepts
    variables_schema = models.JSONField(default=dict, blank=True)
    vendor = models.CharField(max_length=32, blank=True, help_text="Leave blank for all vendors")
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="templates_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class ProvisioningJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial Success"
        FAILED = "failed", "Failed"

    template = models.ForeignKey(ConfigTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    devices = models.ManyToManyField(Device, related_name="provisioning_jobs")
    variables = models.JSONField(default=dict)
    rendered_config = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    initiated_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="provisioning_jobs")
    celery_task_id = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Job #{self.pk} [{self.status}]"


class ProvisioningResult(models.Model):
    """Per-device result within a ProvisioningJob."""
    job = models.ForeignKey(ProvisioningJob, on_delete=models.CASCADE, related_name="results")
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    success = models.BooleanField(default=False)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["executed_at"]


class AuditLog(models.Model):
    """Immutable audit trail for all config actions."""
    class Action(models.TextChoices):
        PUSH_CONFIG = "push_config", "Push Configuration"
        COMPLIANCE_CHECK = "compliance_check", "Compliance Check"
        DRIFT_CHECK = "drift_check", "Drift Check"
        SNAPSHOT = "snapshot", "Config Snapshot"
        DISCOVERY = "discovery", "Device Discovery"

    action = models.CharField(max_length=32, choices=Action.choices)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL)
    detail = models.JSONField(default=dict)
    success = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["action", "timestamp"])]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"
