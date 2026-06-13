from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProvisioningTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('device_type', models.CharField(blank=True, help_text='Leave blank to apply to any device type', max_length=30)),
                ('site', models.CharField(blank=True, help_text='Leave blank for all sites', max_length=20)),
                ('content', models.TextField(help_text='Jinja2 template — use {{ device.hostname }}, etc.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_templates',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Config Template',
                'verbose_name_plural': 'Config Templates',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('template_name', models.CharField(blank=True, max_length=200)),
                ('action', models.CharField(max_length=200)),
                ('config_sent', models.TextField(blank=True, help_text='Full rendered config sent to device')),
                ('config_diff', models.TextField(blank=True, help_text='Unified diff of running-config changes')),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
                    db_index=True, default='pending', max_length=20,
                )),
                ('error_message', models.TextField(blank=True)),
                ('task_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('execution_time', models.FloatField(blank=True, help_text='Task duration in seconds', null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='provisioning_events',
                    to='inventory.device',
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='provisioning_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Audit Log Entry',
                'verbose_name_plural': 'Audit Log',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['device', 'timestamp'], name='provisioni_device_i_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['status', 'timestamp'], name='provisioni_status_timestamp_idx'),
        ),
    ]
