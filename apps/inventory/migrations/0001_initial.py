from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hostname', models.CharField(max_length=100, unique=True)),
                ('ip_address', models.GenericIPAddressField(
                    help_text='Management IP (192.168.100.x)', unique=True,
                )),
                ('wan_ip', models.GenericIPAddressField(
                    blank=True, null=True, help_text='WAN-facing IP address',
                )),
                ('loopback_ip', models.GenericIPAddressField(
                    blank=True, null=True, help_text='Loopback IP / OSPF RID',
                )),
                ('site', models.CharField(
                    choices=[
                        ('sofia', 'Sofia'), ('burgas', 'Burgas'),
                        ('plovdiv', 'Plovdiv'), ('wan', 'WAN Core'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('device_type', models.CharField(
                    choices=[
                        ('router', 'Router'),
                        ('firewall_primary', 'Primary Firewall'),
                        ('firewall_secondary', 'Secondary Firewall'),
                        ('l2_switch', 'L2 Switch'),
                        ('wan_switch', 'WAN Switch'),
                    ],
                    db_index=True, max_length=30,
                )),
                ('vendor', models.CharField(default='Cisco', max_length=50)),
                ('model', models.CharField(blank=True, max_length=100)),
                ('os_version', models.CharField(blank=True, max_length=100)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('up', 'Up'), ('down', 'Down'), ('unknown', 'Unknown')],
                    db_index=True, default='unknown', max_length=20,
                )),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
                ('last_polled', models.DateTimeField(blank=True, null=True)),
                ('snmp_community', models.CharField(default='public', max_length=50)),
                ('snmp_version', models.CharField(
                    choices=[('1', 'v1'), ('2c', 'v2c'), ('3', 'v3')],
                    default='2c', max_length=5,
                )),
                ('ssh_username', models.CharField(blank=True, default='admin', max_length=50)),
                ('ssh_password', models.CharField(blank=True, max_length=1024)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Device',
                'verbose_name_plural': 'Devices',
                'ordering': ['site', 'hostname'],
            },
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['site', 'status'], name='inventory_d_site_status_idx'),
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['site', 'device_type'], name='inventory_d_site_devtype_idx'),
        ),
    ]
