from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings
from .models import Alert, GrafanaDashboard
from apps.inventory.models import Device


@login_required
def dashboard(request):
    context = {
        "device_count": Device.objects.count(),
        "online_count": Device.objects.filter(status="online").count(),
        "offline_count": Device.objects.filter(status="offline").count(),
        "firing_alerts": Alert.objects.filter(status="firing").count(),
        "critical_alerts": Alert.objects.filter(status="firing", severity="critical").count(),
        "recent_alerts": Alert.objects.filter(status="firing").select_related("device").order_by("-received_at")[:10],
        "grafana_url": settings.GRAFANA_URL,
        "dashboards": GrafanaDashboard.objects.all()[:6],
    }
    return render(request, "monitoring/dashboard.html", context)


@login_required
def alerts(request):
    alerts_qs = Alert.objects.select_related("device").order_by("-received_at")[:200]
    return render(request, "monitoring/alerts.html", {"alerts": alerts_qs})


@login_required
def grafana_embed(request):
    dashboards = GrafanaDashboard.objects.all()
    selected_uid = request.GET.get("uid", "")
    selected = dashboards.filter(uid=selected_uid).first() if selected_uid else dashboards.first()
    return render(request, "monitoring/grafana_embed.html", {
        "dashboards": dashboards,
        "selected": selected,
        "grafana_url": settings.GRAFANA_URL,
    })
