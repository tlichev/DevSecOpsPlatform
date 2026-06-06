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
            name="Device",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hostname", models.CharField(max_length=255, unique=True)),
                ("ip_address", models.GenericIPAddressField(unique=True)),
                ("device_type", models.CharField(choices=[("router","Router"),("switch","Switch"),("firewall","Firewall"),("server","Server"),("unknown","Unknown")], default="unknown", max_length=32)),
                ("vendor", models.CharField(choices=[("cisco","Cisco"),("juniper","Juniper"),("arista","Arista"),("paloalto","Palo Alto"),("pfsense","pfSense"),("other","Other")], default="cisco", max_length=32)),
                ("os_version", models.CharField(blank=True, max_length=128)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("online","Online"),("offline","Offline"),("unknown","Unknown"),("maintenance","Maintenance")], default="unknown", max_length=16)),
                ("ssh_username", models.CharField(default="admin", max_length=64)),
                ("ssh_password", models.CharField(blank=True, max_length=128)),
                ("ssh_port", models.PositiveIntegerField(default=22)),
                ("snmp_community", models.CharField(default="public", max_length=64)),
                ("snmp_version", models.CharField(default="2c", max_length=4)),
                ("site", models.CharField(blank=True, max_length=128)),
                ("rack", models.CharField(blank=True, max_length=64)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("discovered_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="devices_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["hostname"]},
        ),
        migrations.CreateModel(
            name="DiscoveryJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subnet", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("pending","Pending"),("running","Running"),("completed","Completed"),("failed","Failed")], default="pending", max_length=16)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("devices_found", models.PositiveIntegerField(default=0)),
                ("devices_added", models.PositiveIntegerField(default=0)),
                ("log", models.TextField(blank=True)),
                ("celery_task_id", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="device", index=models.Index(fields=["ip_address"], name="inventory_d_ip_addr_idx")),
        migrations.AddIndex(model_name="device", index=models.Index(fields=["status"], name="inventory_d_status_idx")),
        migrations.AddIndex(model_name="device", index=models.Index(fields=["device_type"], name="inventory_d_dev_type_idx")),
    ]
