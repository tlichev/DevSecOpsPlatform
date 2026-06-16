import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_ENGINEER = 'engineer'
    ROLE_READONLY = 'readonly'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_ENGINEER, 'Network Engineer'),
        (ROLE_READONLY, 'Read Only'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_READONLY)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    def is_engineer(self):
        return self.role in (self.ROLE_ADMIN, self.ROLE_ENGINEER) or self.is_superuser

    def get_role_display_badge(self):
        colors = {
            self.ROLE_ADMIN: 'danger',
            self.ROLE_ENGINEER: 'primary',
            self.ROLE_READONLY: 'secondary',
        }
        return colors.get(self.role, 'secondary')


class TwoFactorCode(models.Model):
    OTP_EXPIRY_MINUTES = 10

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_codes')
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['user', 'used'], name='accounts_otp_user_used_idx')]

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    @classmethod
    def generate_for(cls, user):
        """Delete any existing codes for the user and create a fresh one."""
        cls.objects.filter(user=user).delete()
        code = f'{secrets.randbelow(1_000_000):06d}'
        return cls.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.OTP_EXPIRY_MINUTES),
        )
