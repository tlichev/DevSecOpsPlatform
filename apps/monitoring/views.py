import logging

from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q

from apps.inventory.models import Device
from .models import Alert

logger = logging.getLogger(__name__)


# ── Home ────────────────────────────────────────────────────────────────────────
@login_required
def monitoring_home(request):
    # Active alert summary
    active_qs   = Alert.objects.filter(status='firing')
    alert_stats = {
        'total':    active_qs.count(),
        'critical': active_qs.filter(severity='critical').count(),
        'warning':  active_qs.filter(severity='warning').count(),
        'unacked':  active_qs.filter(acknowledged=False).count(),
    }

    # Recent firing alerts (top 10)
    recent_alerts = (
        active_qs.filter(acknowledged=False)
        .select_related('acknowledged_by')
        .order_by('-received_at')[:10]
    )

    # Device status counts
    device_stats = {
        'up':      Device.objects.filter(status='up').count(),
        'down':    Device.objects.filter(status='down').count(),
        'unknown': Device.objects.filter(status='unknown').count(),
        'total':   Device.objects.count(),
    }

    # Devices currently marked down
    devices_down = Device.objects.filter(status='down').order_by('site', 'hostname')[:20]

    grafana_url = settings.GRAFANA_BROWSER_URL

    return render(request, 'monitoring/home.html', {
        'alert_stats':   alert_stats,
        'recent_alerts': recent_alerts,
        'device_stats':  device_stats,
        'devices_down':  devices_down,
        'grafana_url':   grafana_url,
    })


# ── Alerts ──────────────────────────────────────────────────────────────────────
@login_required
def alerts(request):
    qs = Alert.objects.select_related('acknowledged_by').order_by('-received_at')

    # Filters
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(alertname__icontains=q) |
            Q(instance__icontains=q) |
            Q(summary__icontains=q)
        )

    status_filter   = request.GET.get('status', '')
    severity_filter = request.GET.get('severity', '')
    site_filter     = request.GET.get('site', '')
    acked_filter    = request.GET.get('acked', '')

    if status_filter   in ('firing', 'resolved'):
        qs = qs.filter(status=status_filter)
    if severity_filter in ('critical', 'warning', 'info'):
        qs = qs.filter(severity=severity_filter)
    if site_filter:
        qs = qs.filter(site=site_filter)
    if acked_filter == 'no':
        qs = qs.filter(acknowledged=False)
    elif acked_filter == 'yes':
        qs = qs.filter(acknowledged=True)

    paginator = Paginator(qs, 30)
    page_obj  = paginator.get_page(request.GET.get('page'))
    sites     = Alert.objects.values_list('site', flat=True).distinct().order_by('site')

    return render(request, 'monitoring/alerts.html', {
        'page_obj':        page_obj,
        'q':               q,
        'status_filter':   status_filter,
        'severity_filter': severity_filter,
        'site_filter':     site_filter,
        'acked_filter':    acked_filter,
        'sites':           [s for s in sites if s],
        'total':           qs.count(),
    })


# ── Grafana Dashboards ──────────────────────────────────────────────────────────
@login_required
def dashboards(request):
    grafana_url = settings.GRAFANA_BROWSER_URL
    # Predefined dashboard links (UID matches the provisioned JSON)
    dashboard_list = [
        {
            'uid':         'netops-overview',
            'title':       'Network Overview',
            'description': 'Interface traffic, device status, and error rates across all sites.',
            'url':         f'{grafana_url}/d/netops-overview/network-overview',
        },
        {
            'uid':         'netops-interfaces',
            'title':       'Interface Traffic',
            'description': 'Per-device interface bandwidth utilisation (ifHCIn/OutOctets).',
            'url':         f'{grafana_url}/d/netops-interfaces/interface-traffic',
        },
        {
            'uid':         'netops-alerts',
            'title':       'Alert History',
            'description': 'AlertManager alert timeline and firing counts.',
            'url':         f'{grafana_url}/d/netops-alerts/alert-history',
        },
    ]
    return render(request, 'monitoring/dashboards.html', {
        'dashboard_list': dashboard_list,
        'grafana_url':    grafana_url,
        'embed_uid':      request.GET.get('uid', 'netops-overview'),
    })
