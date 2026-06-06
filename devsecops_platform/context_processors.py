from django.conf import settings


def platform_settings(request):
    return {
        "GRAFANA_URL": settings.GRAFANA_URL,
        "PROMETHEUS_URL": settings.PROMETHEUS_URL,
        "PLATFORM_NAME": "DevSecOps Platform",
    }
