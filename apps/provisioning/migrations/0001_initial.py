from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("inventory", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("template_type", models.CharField(choices=[("vlan","VLAN Configuration"),("interface","Interface Configuration"),("acl","Access Control List"),("routing","Routing Configuration"),("hardening","Security Hardening Baseline"),("custom","Custom")], default="custom", max_length=32)),
                ("description", models.TextField(blank=True)),
                ("body", models.TextField()),
                ("variables_schema", models.JSONField(blank=True, default=dict)),
                ("vendor", models.CharField(blank=True, help_text="Leave blank for all vendors", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="templates_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ProvisioningJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variables", models.JSONField(default=dict)),
                ("rendered_config", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending","Pending"),("running","Running"),("success","Success"),("partial","Partial Success"),("failed","Failed")], default="pending", max_length=16)),
                ("celery_task_id", models.CharField(blank=True, max_length=64)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="provisioning.configtemplate")),
                ("initiated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provisioning_jobs", to=settings.AUTH_USER_MODEL)),
                ("devices", models.ManyToManyField(related_name="provisioning_jobs", to="inventory.device")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ProvisioningResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("success", models.BooleanField(default=False)),
                ("output", models.TextField(blank=True)),
                ("error", models.TextField(blank=True)),
                ("duration_seconds", models.FloatField(blank=True, null=True)),
                ("executed_at", models.DateTimeField(auto_now_add=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="provisioning.provisioningjob")),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="inventory.device")),
            ],
            options={"ordering": ["executed_at"]},
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("push_config","Push Configuration"),("compliance_check","Compliance Check"),("drift_check","Drift Check"),("snapshot","Config Snapshot"),("discovery","Device Discovery")], max_length=32)),
                ("detail", models.JSONField(default=dict)),
                ("success", models.BooleanField(default=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.device")),
            ],
            options={"ordering": ["-timestamp"]},
        ),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["action", "timestamp"], name="provisioni_action_ts_idx")),
    ]
