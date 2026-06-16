from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0002_rename_monitoring_a_status_severity_idx_monitoring__status_d7b628_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient', models.EmailField()),
                ('alert_state', models.CharField(max_length=20,
                    help_text='firing or resolved')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=True)),
                ('error_msg', models.TextField(blank=True)),
                ('alert', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to='monitoring.alert',
                )),
            ],
            options={
                'ordering': ['-sent_at'],
                'indexes': [
                    models.Index(fields=['alert', 'alert_state'],
                                 name='mon_notif_alert_state_idx'),
                ],
            },
        ),
    ]
