from django.db import models
from django.conf import settings


class Alert(models.Model):
    STATUS_FIRING   = 'firing'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES  = [
        (STATUS_FIRING,   'Firing'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    SEV_CRITICAL = 'critical'
    SEV_WARNING  = 'warning'
    SEV_INFO     = 'info'
    SEV_CHOICES  = [
        (SEV_CRITICAL, 'Critical'),
        (SEV_WARNING,  'Warning'),
        (SEV_INFO,     'Info'),
    ]

    # ── Identity ─────────────────────────────────────────────────────────────
    fingerprint  = models.CharField(max_length=64, unique=True, db_index=True,
                                    help_text='AlertManager fingerprint — prevents duplicates')
    alertname    = models.CharField(max_length=200, db_index=True)
    instance     = models.CharField(max_length=200, blank=True, db_index=True,
                                    help_text='IP / hostname of the source device')
    site         = models.CharField(max_length=50, blank=True, db_index=True)
    severity     = models.CharField(max_length=20, choices=SEV_CHOICES,
                                    default=SEV_WARNING, db_index=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                    default=STATUS_FIRING, db_index=True)

    # ── Content ───────────────────────────────────────────────────────────────
    summary     = models.TextField(blank=True)
    description = models.TextField(blank=True)
    raw_labels  = models.JSONField(default=dict)
    raw_payload = models.JSONField(default=dict,
                                   help_text='Full alert payload from AlertManager')

    # ── Timestamps ────────────────────────────────────────────────────────────
    starts_at   = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at     = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # ── Acknowledgement ───────────────────────────────────────────────────────
    acknowledged    = models.BooleanField(default=False, db_index=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_alerts',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    ack_note        = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['site', 'status']),
        ]

    def __str__(self):
        return f'[{self.severity.upper()}] {self.alertname} — {self.instance} ({self.status})'

    @property
    def is_critical(self):
        return self.severity == self.SEV_CRITICAL

    @property
    def is_active(self):
        return self.status == self.STATUS_FIRING and not self.acknowledged

    def resolve(self):
        from django.utils import timezone
        self.status  = self.STATUS_RESOLVED
        self.ends_at = timezone.now()
        self.save(update_fields=['status', 'ends_at'])


class AlertNotification(models.Model):
    """Tracks every email sent for an alert to prevent duplicate sends."""

    alert       = models.ForeignKey(Alert, on_delete=models.CASCADE,
                                    related_name='notifications')
    recipient   = models.EmailField()
    alert_state = models.CharField(max_length=20,
                                   help_text='"firing" or "resolved"')
    sent_at     = models.DateTimeField(auto_now_add=True)
    success     = models.BooleanField(default=True)
    error_msg   = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes  = [
            models.Index(fields=['alert', 'alert_state'],
                         name='mon_notif_alert_state_idx'),
        ]

    def __str__(self):
        return (f'[{"OK" if self.success else "FAIL"}] '
                f'{self.alert.alertname} → {self.recipient} ({self.alert_state})')
