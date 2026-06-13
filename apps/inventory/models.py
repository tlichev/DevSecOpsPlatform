from django.db import models
from django.utils import timezone


class Device(models.Model):
    # ── Site ────────────────────────────────────────────────────────────────
    SITE_SOFIA   = 'sofia'
    SITE_BURGAS  = 'burgas'
    SITE_PLOVDIV = 'plovdiv'
    SITE_WAN     = 'wan'
    SITE_CHOICES = [
        (SITE_SOFIA,   'Sofia'),
        (SITE_BURGAS,  'Burgas'),
        (SITE_PLOVDIV, 'Plovdiv'),
        (SITE_WAN,     'WAN Core'),
    ]

    # ── Device type ──────────────────────────────────────────────────────────
    TYPE_ROUTER      = 'router'
    TYPE_FW_PRIMARY  = 'firewall_primary'
    TYPE_FW_SECOND   = 'firewall_secondary'
    TYPE_L2_SWITCH   = 'l2_switch'
    TYPE_WAN_SWITCH  = 'wan_switch'
    DEVICE_TYPE_CHOICES = [
        (TYPE_ROUTER,     'Router'),
        (TYPE_FW_PRIMARY, 'Primary Firewall'),
        (TYPE_FW_SECOND,  'Secondary Firewall'),
        (TYPE_L2_SWITCH,  'L2 Switch'),
        (TYPE_WAN_SWITCH, 'WAN Switch'),
    ]

    # ── Status ───────────────────────────────────────────────────────────────
    STATUS_UP      = 'up'
    STATUS_DOWN    = 'down'
    STATUS_UNKNOWN = 'unknown'
    STATUS_CHOICES = [
        (STATUS_UP,      'Up'),
        (STATUS_DOWN,    'Down'),
        (STATUS_UNKNOWN, 'Unknown'),
    ]

    # ── Identity ─────────────────────────────────────────────────────────────
    hostname    = models.CharField(max_length=100, unique=True)
    ip_address  = models.GenericIPAddressField(unique=True, help_text='Management IP (192.168.100.x)')
    wan_ip      = models.GenericIPAddressField(null=True, blank=True, help_text='WAN-facing IP address')
    loopback_ip = models.GenericIPAddressField(null=True, blank=True, help_text='Loopback IP / OSPF RID')

    # ── Classification ────────────────────────────────────────────────────────
    site        = models.CharField(max_length=20, choices=SITE_CHOICES, db_index=True)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES, db_index=True)
    vendor      = models.CharField(max_length=50, default='Cisco')
    model       = models.CharField(max_length=100, blank=True)
    os_version  = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                   default=STATUS_UNKNOWN, db_index=True)
    last_seen   = models.DateTimeField(null=True, blank=True)
    last_polled = models.DateTimeField(null=True, blank=True)

    # ── SNMP ──────────────────────────────────────────────────────────────────
    snmp_community = models.CharField(max_length=50, default='public')
    snmp_version   = models.CharField(
        max_length=5, default='2c',
        choices=[('1', 'v1'), ('2c', 'v2c'), ('3', 'v3')],
    )

    # ── SSH credentials ───────────────────────────────────────────────────────
    ssh_username = models.CharField(max_length=50, blank=True, default='admin')
    # Stores Fernet-encrypted password. Use utils.encrypt_password / decrypt_password.
    ssh_password = models.CharField(max_length=1024, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['site', 'hostname']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        indexes = [
            models.Index(fields=['site', 'status']),
            models.Index(fields=['site', 'device_type']),
        ]

    def __str__(self):
        return f'{self.hostname} ({self.ip_address})'

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def site_color(self):
        return {
            self.SITE_SOFIA:   '#10b981',
            self.SITE_BURGAS:  '#3b82f6',
            self.SITE_PLOVDIV: '#a855f7',
            self.SITE_WAN:     '#f59e0b',
        }.get(self.site, '#6b7280')

    @property
    def device_type_icon(self):
        return {
            self.TYPE_ROUTER:     'bi-router',
            self.TYPE_FW_PRIMARY: 'bi-shield-fill-check',
            self.TYPE_FW_SECOND:  'bi-shield-fill',
            self.TYPE_L2_SWITCH:  'bi-toggles',
            self.TYPE_WAN_SWITCH: 'bi-hdd-rack',
        }.get(self.device_type, 'bi-hdd')

    @property
    def role_short(self):
        """Short role label used in topology.js device dot IDs."""
        return {
            self.TYPE_FW_PRIMARY: 'prim',
            self.TYPE_FW_SECOND:  'sec',
            self.TYPE_L2_SWITCH:  'sw',
            self.TYPE_ROUTER:     'r',
            self.TYPE_WAN_SWITCH: 'sw',
        }.get(self.device_type, self.device_type)

    def get_plaintext_password(self):
        from .utils import decrypt_password
        return decrypt_password(self.ssh_password)

    def set_encrypted_password(self, plaintext):
        from .utils import encrypt_password
        self.ssh_password = encrypt_password(plaintext)

    def get_netmiko_params(self):
        return {
            'device_type': 'cisco_ios',
            'host': self.ip_address,
            'username': self.ssh_username,
            'password': self.get_plaintext_password(),
            'timeout': 30,
            'session_timeout': 60,
        }

    def mark_seen(self):
        now = timezone.now()
        Device.objects.filter(pk=self.pk).update(
            status=self.STATUS_UP,
            last_seen=now,
            last_polled=now,
        )

    def mark_down(self):
        Device.objects.filter(pk=self.pk).update(
            status=self.STATUS_DOWN,
            last_polled=timezone.now(),
        )
