from django.db import models
from django.conf import settings


class ProvisioningTemplate(models.Model):
    """User-editable config template stored in the database."""
    name        = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    device_type = models.CharField(max_length=30, blank=True,
                                   help_text='Leave blank to apply to any device type')
    site        = models.CharField(max_length=20, blank=True,
                                   help_text='Leave blank for all sites')
    content     = models.TextField(help_text='Jinja2 template — use {{ device.hostname }}, etc.')
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_templates',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Config Template'
        verbose_name_plural = 'Config Templates'

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED  = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED,  'Failed'),
    ]

    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='provisioning_events',
    )
    device  = models.ForeignKey(
        'inventory.Device', on_delete=models.CASCADE,
        related_name='provisioning_events',
    )

    template_name  = models.CharField(max_length=200, blank=True)
    action         = models.CharField(max_length=200)
    config_sent    = models.TextField(blank=True, help_text='Full rendered config sent to device')
    config_diff    = models.TextField(blank=True, help_text='Unified diff of running-config changes')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                      default=STATUS_PENDING, db_index=True)
    error_message  = models.TextField(blank=True)
    task_id        = models.CharField(max_length=100, blank=True, db_index=True)
    execution_time = models.FloatField(null=True, blank=True,
                                       help_text='Task duration in seconds')
    timestamp      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log Entry'
        verbose_name_plural = 'Audit Log'
        indexes = [
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['status', 'timestamp']),
        ]

    def __str__(self):
        return (
            f'{self.timestamp:%Y-%m-%d %H:%M} | '
            f'{self.device.hostname} | {self.template_name or self.action} | {self.status}'
        )

    @property
    def success(self):
        return self.status == self.STATUS_SUCCESS

    @property
    def duration_display(self):
        if self.execution_time is None:
            return '—'
        return f'{self.execution_time:.1f}s'
