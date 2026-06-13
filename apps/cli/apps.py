from django.apps import AppConfig


class CliConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cli'
    verbose_name = 'CLI Console'
