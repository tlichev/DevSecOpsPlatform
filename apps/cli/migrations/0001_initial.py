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
            name='CLISession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cli_sessions',
                    to='inventory.device',
                )),
                ('user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='cli_sessions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'CLI Session',
                'verbose_name_plural': 'CLI Sessions',
                'ordering': ['-last_used'],
            },
        ),
        migrations.CreateModel(
            name='CLICommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.CharField(max_length=500)),
                ('output', models.TextField(blank=True)),
                ('is_error', models.BooleanField(default=False)),
                ('executed_at', models.DateTimeField(auto_now_add=True)),
                ('duration_ms', models.IntegerField(default=0)),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commands',
                    to='cli.clisession',
                )),
            ],
            options={
                'verbose_name': 'CLI Command',
                'verbose_name_plural': 'CLI Commands',
                'ordering': ['executed_at'],
            },
        ),
    ]
