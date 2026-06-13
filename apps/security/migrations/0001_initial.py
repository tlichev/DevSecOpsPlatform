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
            name='ComplianceRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(blank=True, db_index=True, max_length=50, help_text='e.g. SSH, AAA, NTP, SNMP, Logging')),
                ('pattern', models.CharField(max_length=500, help_text='Python regex searched against the full running-config')),
                ('match_means_pass', models.BooleanField(default=True)),
                ('device_types', models.JSONField(blank=True, default=list)),
                ('severity', models.CharField(
                    choices=[('critical', 'Critical'), ('warning', 'Warning'), ('info', 'Info')],
                    db_index=True, default='warning', max_length=20,
                )),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('remediation', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Compliance Rule',
                'verbose_name_plural': 'Compliance Rules',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='GoldenConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_type', models.CharField(db_index=True, max_length=30, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('content', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='golden_configs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Golden Config',
                'verbose_name_plural': 'Golden Configs',
                'ordering': ['device_type'],
            },
        ),
        migrations.CreateModel(
            name='ComplianceResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('pass', 'Pass'), ('fail', 'Fail'), ('error', 'Error'), ('skipped', 'Skipped')],
                    db_index=True, default='fail', max_length=20,
                )),
                ('evidence', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('task_id', models.CharField(blank=True, max_length=100)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='compliance_results',
                    to='inventory.device',
                )),
                ('rule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='results',
                    to='security.compliancerule',
                )),
            ],
            options={
                'verbose_name': 'Compliance Result',
                'verbose_name_plural': 'Compliance Results',
                'ordering': ['-checked_at'],
                'get_latest_by': 'checked_at',
            },
        ),
        migrations.CreateModel(
            name='DriftResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('clean', 'Clean'), ('drifted', 'Drifted'), ('error', 'Error')],
                    db_index=True, default='drifted', max_length=20,
                )),
                ('diff', models.TextField(blank=True)),
                ('drift_lines', models.IntegerField(default=0)),
                ('running_config', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('task_id', models.CharField(blank=True, max_length=100)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='drift_results',
                    to='inventory.device',
                )),
                ('golden_config', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='drift_results',
                    to='security.goldenconfig',
                )),
            ],
            options={
                'verbose_name': 'Drift Result',
                'verbose_name_plural': 'Drift Results',
                'ordering': ['-checked_at'],
                'get_latest_by': 'checked_at',
            },
        ),
        migrations.AddIndex(
            model_name='complianceresult',
            index=models.Index(fields=['device', 'rule', 'checked_at'], name='security_cr_dev_rule_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='complianceresult',
            index=models.Index(fields=['device', 'status'], name='security_cr_dev_status_idx'),
        ),
        migrations.AddIndex(
            model_name='driftresult',
            index=models.Index(fields=['device', 'checked_at'], name='security_dr_dev_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='driftresult',
            index=models.Index(fields=['device', 'status'], name='security_dr_dev_status_idx'),
        ),
    ]
