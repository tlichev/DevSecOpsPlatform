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
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("admin","Admin"),("network_engineer","Network Engineer"),("read_only","Read-Only")], default="read_only", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ComplianceRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField()),
                ("check_command", models.CharField(max_length=255)),
                ("expected_pattern", models.CharField(help_text="Regex that must match for compliance", max_length=512)),
                ("must_match", models.BooleanField(default=True, help_text="If False, pattern must NOT match")),
                ("severity", models.CharField(choices=[("critical","Critical"),("high","High"),("medium","Medium"),("low","Low")], default="high", max_length=16)),
                ("remediation", models.TextField(blank=True, help_text="Jinja2 config snippet to remediate")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["severity", "name"]},
        ),
        migrations.CreateModel(
            name="ComplianceCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("compliant","Compliant"),("non_compliant","Non-Compliant"),("error","Error")], max_length=16)),
                ("output", models.TextField(blank=True)),
                ("detail", models.TextField(blank=True)),
                ("checked_at", models.DateTimeField(auto_now_add=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="compliance_checks", to="inventory.device")),
                ("rule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checks", to="security.compliancerule")),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-checked_at"]},
        ),
        migrations.CreateModel(
            name="ConfigSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("config", models.TextField()),
                ("is_golden", models.BooleanField(default=False)),
                ("taken_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.CharField(blank=True, max_length=255)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="config_snapshots", to="inventory.device")),
                ("taken_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-taken_at"]},
        ),
        migrations.CreateModel(
            name="DriftReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("clean","No Drift"),("drifted","Drift Detected"),("error","Error")], default="clean", max_length=16)),
                ("diff", models.TextField(blank=True)),
                ("checked_at", models.DateTimeField(auto_now_add=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="drift_reports", to="inventory.device")),
                ("golden_snapshot", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="drift_reports_as_golden", to="security.configsnapshot")),
                ("current_snapshot", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="drift_reports_as_current", to="security.configsnapshot")),
            ],
            options={"ordering": ["-checked_at"]},
        ),
        migrations.AddIndex(model_name="compliancecheck", index=models.Index(fields=["device", "rule", "checked_at"], name="security_cc_dev_rule_idx")),
        migrations.AddIndex(model_name="configsnapshot", index=models.Index(fields=["device", "is_golden"], name="security_cs_dev_golden_idx")),
    ]
