from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from apps.inventory.models import Device
from .models import ProvisioningTemplate, AuditLog
from .template_engine import list_all_templates


def _engineer_required(func):
    """Decorator: login + engineer/admin role."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_engineer() or request.user.is_superuser):
            messages.error(request, 'Engineer or Admin role required.')
            return redirect('inventory:dashboard')
        return func(request, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Home ────────────────────────────────────────────────────────────────────────
@login_required
def provisioning_home(request):
    db_templates = ProvisioningTemplate.objects.filter(is_active=True).order_by('name')
    file_templates = list_all_templates()
    recent_logs = (
        AuditLog.objects
        .select_related('device', 'user')
        .order_by('-timestamp')[:20]
    )
    stats = {
        'total_pushes':   AuditLog.objects.count(),
        'successful':     AuditLog.objects.filter(status=AuditLog.STATUS_SUCCESS).count(),
        'failed':         AuditLog.objects.filter(status=AuditLog.STATUS_FAILED).count(),
        'db_templates':   db_templates.count(),
        'file_templates': len([t for t in file_templates if t['source'] == 'file']),
    }
    return render(request, 'provisioning/home.html', {
        'db_templates':   db_templates,
        'file_templates': file_templates,
        'recent_logs':    recent_logs,
        'stats':          stats,
    })


# ── Push config ─────────────────────────────────────────────────────────────────
@_engineer_required
def push_config(request):
    sites = Device.objects.values_list('site', flat=True).distinct().order_by('site')
    device_types = Device.objects.values_list('device_type', flat=True).distinct().order_by()
    all_templates = list_all_templates()
    devices = Device.objects.filter(status='up').order_by('site', 'hostname')
    return render(request, 'provisioning/push_config.html', {
        'devices':       devices,
        'sites':         list(sites),
        'device_types':  list(device_types),
        'all_templates': all_templates,
    })


# ── Audit log ───────────────────────────────────────────────────────────────────
@login_required
def audit_log(request):
    qs = AuditLog.objects.select_related('device', 'user').order_by('-timestamp')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(device__hostname__icontains=q) |
            Q(template_name__icontains=q) |
            Q(user__username__icontains=q)
        )

    status_filter = request.GET.get('status', '')
    if status_filter in ('pending', 'success', 'failed'):
        qs = qs.filter(status=status_filter)

    site_filter = request.GET.get('site', '')
    if site_filter:
        qs = qs.filter(device__site=site_filter)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    sites = Device.objects.values_list('site', flat=True).distinct().order_by('site')

    return render(request, 'provisioning/audit_log.html', {
        'page_obj':      page_obj,
        'q':             q,
        'status_filter': status_filter,
        'site_filter':   site_filter,
        'sites':         list(sites),
        'total':         qs.count(),
    })


# ── Audit detail ────────────────────────────────────────────────────────────────
@login_required
def audit_detail(request, pk):
    log = get_object_or_404(
        AuditLog.objects.select_related('device', 'user'), pk=pk
    )
    return render(request, 'provisioning/audit_detail.html', {'log': log})
