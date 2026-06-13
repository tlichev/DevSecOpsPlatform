from django.contrib.auth.models import AbstractUser
from django.db import models


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
