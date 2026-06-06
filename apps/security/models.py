from django.db import models
from django.contrib.auth.models import User
from apps.inventory.models import Device


class ComplianceRule(models.Model):
    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    # Command to run on device, regex to match in output
    check_command = models.CharField(max_length=255)
    expected_pattern = models.CharField(max_length=512, help_text="Regex that must match for compliance")
    must_match = models.BooleanField(default=True, help_text="If False, pattern must NOT match (e.g. telnet disabled)")
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.HIGH)
    remediation = models.TextField(blank=True, help_text="Jinja2 config snippet to remediate")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["severity", "name"]

    def __str__(self):
        return f"{self.name} [{self.severity}]"


class ComplianceCheck(models.Model):
    class Status(models.TextChoices):
        COMPLIANT = "compliant", "Compliant"
        NON_COMPLIANT = "non_compliant", "Non-Compliant"
        ERROR = "error", "Error"

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="compliance_checks")
    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE, related_name="checks")
    status = models.CharField(max_length=16, choices=Status.choices)
    output = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    initiated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["device", "rule", "checked_at"])]

    def __str__(self):
        return f"{self.device.hostname} — {self.rule.name}: {self.status}"


class ConfigSnapshot(models.Model):
    """Golden config snapshot for drift detection."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="config_snapshots")
    config = models.TextField()
    is_golden = models.BooleanField(default=False)
    taken_at = models.DateTimeField(auto_now_add=True)
    taken_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-taken_at"]
        indexes = [models.Index(fields=["device", "is_golden"])]

    def __str__(self):
        return f"Snapshot of {self.device.hostname} at {self.taken_at}"


class DriftReport(models.Model):
    class Status(models.TextChoices):
        CLEAN = "clean", "No Drift"
        DRIFTED = "drifted", "Drift Detected"
        ERROR = "error", "Error"

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="drift_reports")
    golden_snapshot = models.ForeignKey(ConfigSnapshot, null=True, on_delete=models.SET_NULL, related_name="drift_reports_as_golden")
    current_snapshot = models.ForeignKey(ConfigSnapshot, null=True, on_delete=models.SET_NULL, related_name="drift_reports_as_current")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CLEAN)
    diff = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]

    def __str__(self):
        return f"Drift {self.device.hostname}: {self.status} @ {self.checked_at}"


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        NETWORK_ENGINEER = "network_engineer", "Network Engineer"
        READ_ONLY = "read_only", "Read-Only"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.READ_ONLY)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
