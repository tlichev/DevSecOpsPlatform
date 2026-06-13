from django.db import models
from django.conf import settings


class CLISession(models.Model):
    device    = models.ForeignKey(
        'inventory.Device', on_delete=models.CASCADE, related_name='cli_sessions',
    )
    user      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='cli_sessions',
    )
    name      = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used']
        verbose_name = 'CLI Session'
        verbose_name_plural = 'CLI Sessions'

    def __str__(self):
        label = self.name or f'Session #{self.pk}'
        return f'{self.device.hostname} — {label}'

    @property
    def command_count(self):
        return self.commands.count()


class CLICommand(models.Model):
    session     = models.ForeignKey(CLISession, on_delete=models.CASCADE, related_name='commands')
    command     = models.CharField(max_length=500)
    output      = models.TextField(blank=True)
    is_error    = models.BooleanField(default=False)
    executed_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.IntegerField(default=0)

    class Meta:
        ordering = ['executed_at']
        verbose_name = 'CLI Command'
        verbose_name_plural = 'CLI Commands'

    def __str__(self):
        return f'{self.session.device.hostname}# {self.command}'
