from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.CharField(
                    db_index=True, help_text='AlertManager fingerprint — prevents duplicates',
                    max_length=64, unique=True,
                )),
                ('alertname', models.CharField(db_index=True, max_length=200)),
                ('instance', models.CharField(
                    blank=True, db_index=True, max_length=200,
                    help_text='IP / hostname of the source device',
                )),
                ('site', models.CharField(blank=True, db_index=True, max_length=50)),
                ('severity', models.CharField(
                    choices=[('critical', 'Critical'), ('warning', 'Warning'), ('info', 'Info')],
                    db_index=True, default='warning', max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('firing', 'Firing'), ('resolved', 'Resolved')],
                    db_index=True, default='firing', max_length=20,
                )),
                ('summary', models.TextField(blank=True)),
                ('description', models.TextField(blank=True)),
                ('raw_labels', models.JSONField(default=dict)),
                ('raw_payload', models.JSONField(
                    default=dict, help_text='Full alert payload from AlertManager',
                )),
                ('starts_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('ends_at', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('acknowledged', models.BooleanField(db_index=True, default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('ack_note', models.TextField(blank=True)),
                ('acknowledged_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='acknowledged_alerts',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Alert',
                'verbose_name_plural': 'Alerts',
                'ordering': ['-received_at'],
            },
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['status', 'severity'], name='monitoring_a_status_severity_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['site', 'status'], name='monitoring_a_site_status_idx'),
        ),
    ]
