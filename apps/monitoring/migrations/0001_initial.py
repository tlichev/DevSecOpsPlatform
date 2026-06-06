from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrafanaDashboard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("uid", models.CharField(max_length=64, unique=True)),
                ("panel_id", models.IntegerField(blank=True, null=True)),
                ("description", models.TextField(blank=True)),
                ("embed_url", models.CharField(blank=True, max_length=512)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["order", "title"]},
        ),
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alert_name", models.CharField(max_length=255)),
                ("severity", models.CharField(choices=[("critical","Critical"),("warning","Warning"),("info","Info"),("resolved","Resolved")], default="info", max_length=16)),
                ("status", models.CharField(default="firing", max_length=16)),
                ("instance", models.CharField(blank=True, max_length=255)),
                ("labels", models.JSONField(default=dict)),
                ("annotations", models.JSONField(default=dict)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("generator_url", models.URLField(blank=True)),
                ("fingerprint", models.CharField(blank=True, db_index=True, max_length=64)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("acknowledged", models.BooleanField(default=False)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alerts", to="inventory.device")),
            ],
            options={"ordering": ["-received_at"]},
        ),
        migrations.AddIndex(model_name="alert", index=models.Index(fields=["status", "severity"], name="monitoring_status_sev_idx")),
        migrations.AddIndex(model_name="alert", index=models.Index(fields=["alert_name"], name="monitoring_alert_name_idx")),
    ]
