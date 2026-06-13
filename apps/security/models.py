import re
from django.db import models
from django.conf import settings


class ComplianceRule(models.Model):
    SEV_CRITICAL = 'critical'
    SEV_WARNING  = 'warning'
    SEV_INFO     = 'info'
    SEV_CHOICES  = [
        (SEV_CRITICAL, 'Critical'),
        (SEV_WARNING,  'Warning'),
        (SEV_INFO,     'Info'),
    ]

    name             = models.CharField(max_length=200, unique=True)
    description      = models.TextField(blank=True)
    category         = models.CharField(max_length=50, blank=True, db_index=True,
                                        help_text='e.g. SSH, AAA, NTP, SNMP, Logging')
    pattern          = models.CharField(max_length=500,
                                        help_text='Python regex searched against the full running-config')
    match_means_pass = models.BooleanField(default=True,
                                           help_text='True = pattern present ⇒ PASS; '
                                                     'False = pattern present ⇒ FAIL (absence check)')
    device_types     = models.JSONField(default=list, blank=True,
                                        help_text='List of device_type slugs this rule applies to. '
                                                  'Empty list = all device types.')
    severity         = models.CharField(max_length=20, choices=SEV_CHOICES,
                                        default=SEV_WARNING, db_index=True)
    is_active        = models.BooleanField(default=True, db_index=True)
    remediation      = models.TextField(blank=True,
                                        help_text='CLI commands to fix this finding')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Compliance Rule'
        verbose_name_plural = 'Compliance Rules'

    def __str__(self):
        return f'[{self.category}] {self.name}'

    def check(self, running_config: str) -> bool:
        """Return True if the device PASSES this rule."""
        matched = bool(re.search(self.pattern, running_config, re.MULTILINE | re.IGNORECASE))
        return matched if self.match_means_pass else not matched

    def get_evidence(self, running_config: str) -> str:
        """Return the first matching line (or '' if no match)."""
        m = re.search(self.pattern, running_config, re.MULTILINE | re.IGNORECASE)
        return m.group(0)[:500] if m else ''


class ComplianceResult(models.Model):
    STATUS_PASS    = 'pass'
    STATUS_FAIL    = 'fail'
    STATUS_ERROR   = 'error'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PASS,    'Pass'),
        (STATUS_FAIL,    'Fail'),
        (STATUS_ERROR,   'Error'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    device    = models.ForeignKey(
        'inventory.Device', on_delete=models.CASCADE,
        related_name='compliance_results',
    )
    rule      = models.ForeignKey(
        ComplianceRule, on_delete=models.CASCADE,
        related_name='results',
    )
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                 default=STATUS_FAIL, db_index=True)
    evidence  = models.TextField(blank=True,
                                 help_text='Matched config line or empty string')
    error_message = models.TextField(blank=True)
    checked_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    task_id       = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-checked_at']
        verbose_name = 'Compliance Result'
        verbose_name_plural = 'Compliance Results'
        get_latest_by = 'checked_at'
        indexes = [
            models.Index(fields=['device', 'rule', 'checked_at']),
            models.Index(fields=['device', 'status']),
        ]

    def __str__(self):
        return f'{self.device.hostname} | {self.rule.name} | {self.status}'

    @property
    def passed(self):
        return self.status == self.STATUS_PASS


class GoldenConfig(models.Model):
    """Expected ("golden") configuration for a device type."""
    device_type = models.CharField(max_length=30, unique=True, db_index=True,
                                   help_text='Must match Device.device_type slug')
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content     = models.TextField(help_text='Expected running-config lines — one per line. '
                                             'Used as the baseline for drift detection.')
    is_active   = models.BooleanField(default=True)
    version     = models.PositiveIntegerField(default=1)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='golden_configs',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['device_type']
        verbose_name = 'Golden Config'
        verbose_name_plural = 'Golden Configs'

    def __str__(self):
        return f'Golden Config [{self.device_type}] v{self.version}'


class DriftResult(models.Model):
    STATUS_CLEAN   = 'clean'
    STATUS_DRIFTED = 'drifted'
    STATUS_ERROR   = 'error'
    STATUS_CHOICES = [
        (STATUS_CLEAN,   'Clean'),
        (STATUS_DRIFTED, 'Drifted'),
        (STATUS_ERROR,   'Error'),
    ]

    device        = models.ForeignKey(
        'inventory.Device', on_delete=models.CASCADE,
        related_name='drift_results',
    )
    golden_config = models.ForeignKey(
        GoldenConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='drift_results',
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                     default=STATUS_DRIFTED, db_index=True)
    diff          = models.TextField(blank=True, help_text='Unified diff: golden → actual')
    drift_lines   = models.IntegerField(default=0,
                                        help_text='Number of +/- lines in the diff')
    running_config = models.TextField(blank=True, help_text='Running-config snapshot at check time')
    error_message  = models.TextField(blank=True)
    checked_at     = models.DateTimeField(auto_now_add=True, db_index=True)
    task_id        = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-checked_at']
        verbose_name = 'Drift Result'
        verbose_name_plural = 'Drift Results'
        get_latest_by = 'checked_at'
        indexes = [
            models.Index(fields=['device', 'checked_at']),
            models.Index(fields=['device', 'status']),
        ]

    def __str__(self):
        return (
            f'{self.device.hostname} | {self.status} | '
            f'{self.drift_lines} line(s) drift | {self.checked_at:%Y-%m-%d %H:%M}'
        )

    @property
    def is_clean(self):
        return self.status == self.STATUS_CLEAN
