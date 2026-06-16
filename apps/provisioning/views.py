import re

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from jinja2 import Environment, TemplateSyntaxError

from apps.inventory.models import Device
from .models import ProvisioningTemplate, AuditLog
from .template_engine import list_all_templates, TEMPLATES_DIR, list_file_templates

_SAFE_STEM = re.compile(r'^[a-z0-9_\-]+$')

_TEMPLATE_VARS = [
    'hostname', 'ip_address', 'wan_ip', 'loopback_ip',
    'site', 'site_label', 'device_type', 'vendor', 'model',
    'os_version', 'snmp_community', 'ssh_username',
    'MGMT_NETWORK', 'NTP_SERVER', 'SYSLOG_SERVER',
]


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


# ── File template management ─────────────────────────────────────────────────

def _resolve_template_path(stem):
    """Return a safe Path for stem.j2, or None if the name is invalid."""
    if not _SAFE_STEM.match(stem):
        return None
    path = (TEMPLATES_DIR / stem).with_suffix('.j2')
    try:
        path.resolve().relative_to(TEMPLATES_DIR.resolve())
    except ValueError:
        return None
    return path


@_engineer_required
def file_template_list(request):
    templates = list_file_templates()
    return render(request, 'provisioning/file_template_list.html', {
        'templates': templates,
    })


@login_required
def file_template_detail(request, stem):
    path = _resolve_template_path(stem)
    if not path or not path.exists():
        messages.error(request, f'Template "{stem}.j2" not found.')
        return redirect('provisioning:file_template_list')
    content = path.read_text(encoding='utf-8')
    return render(request, 'provisioning/file_template_detail.html', {
        'stem':    stem,
        'content': content,
        'size':    path.stat().st_size,
    })


@_engineer_required
def file_template_create(request):
    if request.method == 'POST':
        stem    = request.POST.get('name', '').strip().lower().replace(' ', '_')
        content = request.POST.get('content', '')

        if not _SAFE_STEM.match(stem):
            messages.error(request, 'Invalid name — use only lowercase letters, digits, underscores, and hyphens.')
            return render(request, 'provisioning/file_template_form.html', {
                'stem': stem, 'content': content, 'mode': 'create',
                'template_vars': _TEMPLATE_VARS,
            })

        path = _resolve_template_path(stem)
        if path.exists():
            messages.error(request, f'"{stem}.j2" already exists. Edit it instead.')
            return render(request, 'provisioning/file_template_form.html', {
                'stem': stem, 'content': content, 'mode': 'create',
                'template_vars': _TEMPLATE_VARS,
            })

        try:
            Environment().parse(content)
        except TemplateSyntaxError as exc:
            messages.error(request, f'Jinja2 syntax error: {exc}')
            return render(request, 'provisioning/file_template_form.html', {
                'stem': stem, 'content': content, 'mode': 'create',
                'template_vars': _TEMPLATE_VARS,
            })

        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        messages.success(request, f'Template "{stem}.j2" created.')
        return redirect('provisioning:file_template_detail', stem=stem)

    return render(request, 'provisioning/file_template_form.html', {
        'stem': '', 'content': '', 'mode': 'create',
        'template_vars': _TEMPLATE_VARS,
    })


@_engineer_required
def file_template_edit(request, stem):
    path = _resolve_template_path(stem)
    if not path or not path.exists():
        messages.error(request, f'Template "{stem}.j2" not found.')
        return redirect('provisioning:file_template_list')

    if request.method == 'POST':
        content = request.POST.get('content', '')
        try:
            Environment().parse(content)
        except TemplateSyntaxError as exc:
            messages.error(request, f'Jinja2 syntax error: {exc}')
            return render(request, 'provisioning/file_template_form.html', {
                'stem': stem, 'content': content, 'mode': 'edit',
                'template_vars': _TEMPLATE_VARS,
            })
        path.write_text(content, encoding='utf-8')
        messages.success(request, f'Template "{stem}.j2" saved.')
        return redirect('provisioning:file_template_detail', stem=stem)

    content = path.read_text(encoding='utf-8')
    return render(request, 'provisioning/file_template_form.html', {
        'stem': stem, 'content': content, 'mode': 'edit',
        'template_vars': _TEMPLATE_VARS,
    })


@_engineer_required
def file_template_delete(request, stem):
    if request.method != 'POST':
        return redirect('provisioning:file_template_list')
    path = _resolve_template_path(stem)
    if path and path.exists():
        path.unlink()
        messages.success(request, f'Template "{stem}.j2" deleted.')
    else:
        messages.error(request, f'Template "{stem}.j2" not found.')
    return redirect('provisioning:file_template_list')
