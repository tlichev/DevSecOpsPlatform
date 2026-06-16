from django.db import migrations, models
from django.core.serializers.json import DjangoJSONEncoder


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0003_alertnotification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alert',
            name='raw_labels',
            field=models.JSONField(default=dict, encoder=DjangoJSONEncoder),
        ),
        migrations.AlterField(
            model_name='alert',
            name='raw_payload',
            field=models.JSONField(
                default=dict,
                encoder=DjangoJSONEncoder,
                help_text='Full alert payload from AlertManager',
            ),
        ),
    ]
