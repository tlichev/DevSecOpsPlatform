import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Count, Q
from django.shortcuts import render, get_object_or_404, redirect

from apps.inventory.models import Device
from .models import ComplianceRule, ComplianceResult, GoldenConfig, DriftResult

logger = logging.getLogger(__name__)


def _engineer_required(func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_engineer() or request.user.is_superuser):
            messages.error(request, 'Engineer or Admin role required.')
            return redirect('security:home')
        return func(request, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def _latest_results_per_device():
    """Return the latest ComplianceResult ID per (device, rule) pair."""
    from django.db.models import Max
    ids = (
        ComplianceResult.objects
        .values('device', 'rule')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    return ComplianceResult.objects.filter(id__in=ids).select_related('device', 'rule')


def _device_compliance_score(device_id):
    """Return (pass_count, total, score_pct) for the latest check run on a device."""
    ids = (
        ComplianceResult.objects
        .filter(device_id=device_id)
        .values('rule')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    qs    = ComplianceResult.objects.filter(id__in=ids)
    total = qs.filter(status__in=['pass', 'fail']).count()
    passed = qs.filter(status='pass').count()
    score  = round(passed / total * 100) if total > 0 else None
    return passed, total, score


# ── Home ───────────────────────────────────────────────────────────────────────
@login_required
def security_home(request):
    # Latest result per device+rule
    latest_qs = _latest_results_per_device()
    total_checks = latest_qs.count()
    total_pass   = latest_qs.filter(status='pass').count()
    total_fail   = latest_qs.filter(status='fail').count()
    overall_score = round(total_pass / total_checks * 100) if total_checks else None

    # Drift summary
    latest_drift_ids = (
        DriftResult.objects
        .values('device')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    drift_qs      = DriftResult.objects.filter(id__in=latest_drift_ids)
    total_drifted = drift_qs.filter(status='drifted').count()
    total_clean   = drift_qs.filter(status='clean').count()

    # Per-device score table (top 10 worst first)
    device_scores = []
    devices_with_results = (
        ComplianceResult.objects
        .values_list('device_id', flat=True)
        .distinct()
    )
    for did in devices_with_results:
        passed, total, score = _device_compliance_score(did)
        if score is not None:
            try:
                dev = Device.objects.get(pk=did)
                device_scores.append({
                    'device': dev,
                    'score':  score,
                    'pass':   passed,
                    'total':  total,
                    'fail':   total - passed,
                })
            except Device.DoesNotExist:
                pass

    device_scores.sort(key=lambda x: x['score'])

    # Most recent failures
    recent_fails = (
        latest_qs.filter(status='fail')
        .order_by('-checked_at')[:10]
    )

    rules_count = ComplianceRule.objects.filter(is_active=True).count()

    return render(request, 'security/home.html', {
        'overall_score':  overall_score,
        'total_checks':   total_checks,
        'total_pass':     total_pass,
        'total_fail':     total_fail,
        'total_drifted':  total_drifted,
        'total_clean':    total_clean,
        'device_scores':  device_scores,
        'recent_fails':   recent_fails,
        'rules_count':    rules_count,
        'checked':        bool(total_checks),
    })


# ── Compliance ──────────────────────────────────────────────────────────────────
@login_required
def compliance(request):
    devices_with_results = (
        ComplianceResult.objects
        .values_list('device_id', flat=True)
        .distinct()
    )
    rows = []
    for did in devices_with_results:
        passed, total, score = _device_compliance_score(did)
        try:
            dev = Device.objects.get(pk=did)
            latest = (
                ComplianceResult.objects
                .filter(device_id=did)
                .order_by('-checked_at')
                .first()
            )
            rows.append({
                'device':      dev,
                'score':       score,
                'pass':        passed,
                'total':       total,
                'fail':        total - passed,
                'last_checked': latest.checked_at if latest else None,
            })
        except Device.DoesNotExist:
            pass

    rows.sort(key=lambda x: (x['score'] or 0))
    rules = ComplianceRule.objects.filter(is_active=True).order_by('category', 'name')

    return render(request, 'security/compliance.html', {
        'rows':  rows,
        'rules': rules,
    })


# ── Compliance detail per device ────────────────────────────────────────────────
@login_required
def compliance_device(request, device_id: int):
    device = get_object_or_404(Device, pk=device_id)
    passed, total, score = _device_compliance_score(device_id)

    ids = (
        ComplianceResult.objects
        .filter(device_id=device_id)
        .values('rule')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    results = (
        ComplianceResult.objects
        .filter(id__in=ids)
        .select_related('rule')
        .order_by('rule__category', 'rule__name')
    )
    return render(request, 'security/compliance_device.html', {
        'device':  device,
        'results': results,
        'score':   score,
        'pass':    passed,
        'total':   total,
        'fail':    total - passed,
    })


# ── Drift detection ─────────────────────────────────────────────────────────────
@login_required
def drift_detection(request):
    latest_ids = (
        DriftResult.objects
        .values('device')
        .annotate(latest=Max('id'))
        .values_list('latest', flat=True)
    )
    drift_rows = (
        DriftResult.objects
        .filter(id__in=latest_ids)
        .select_related('device', 'golden_config')
        .order_by('-drift_lines', 'device__site')
    )
    golden_configs = GoldenConfig.objects.filter(is_active=True)
    return render(request, 'security/drift.html', {
        'drift_rows':    drift_rows,
        'golden_configs': golden_configs,
    })


# ── Drift detail per device ─────────────────────────────────────────────────────
@login_required
def drift_device(request, device_id: int):
    device = get_object_or_404(Device, pk=device_id)
    history = (
        DriftResult.objects
        .filter(device=device)
        .select_related('golden_config')
        .order_by('-checked_at')[:20]
    )
    latest = history.first()
    return render(request, 'security/drift_device.html', {
        'device':  device,
        'latest':  latest,
        'history': history,
    })
