import difflib
import logging
import time

from celery import shared_task, group

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fetch_running_config(device) -> str:
    """SSH to device, return `show running-config` output."""
    from netmiko import ConnectHandler
    params = device.get_netmiko_params()
    with ConnectHandler(**params) as conn:
        return conn.send_command('show running-config', read_timeout=90)


def _score(pass_count: int, total: int) -> int:
    if total == 0:
        return 100
    return round(pass_count / total * 100)


# ── Single device compliance check ─────────────────────────────────────────────

@shared_task(bind=True, name='security.run_compliance', queue='default',
             max_retries=1, default_retry_delay=15)
def run_compliance_checks(self, device_id: int) -> dict:
    """
    Fetch running-config via SSH, evaluate all active ComplianceRules,
    and write ComplianceResult records for this device.
    """
    from apps.inventory.models import Device
    from .models import ComplianceRule, ComplianceResult

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return {'error': 'device_not_found'}

    rules = ComplianceRule.objects.filter(is_active=True)

    # Filter rules applicable to this device type
    applicable = [
        r for r in rules
        if not r.device_types or device.device_type in r.device_types
    ]

    if not applicable:
        return {'device': device.hostname, 'skipped': True, 'reason': 'no applicable rules'}

    # Fetch running-config
    running_config = ''
    fetch_error = ''
    try:
        running_config = _fetch_running_config(device)
        device.mark_seen()
    except Exception as exc:
        fetch_error = str(exc)
        logger.warning('compliance fetch failed %s: %s', device.hostname, exc)

    task_id = self.request.id or ''
    results = {'pass': 0, 'fail': 0, 'error': 0, 'skipped': 0}

    for rule in applicable:
        if fetch_error:
            status   = ComplianceResult.STATUS_ERROR
            evidence = ''
            error_msg = f'Could not fetch config: {fetch_error}'
        else:
            try:
                passed   = rule.check(running_config)
                evidence = rule.get_evidence(running_config)
                status   = ComplianceResult.STATUS_PASS if passed else ComplianceResult.STATUS_FAIL
                error_msg = ''
            except Exception as exc:
                status    = ComplianceResult.STATUS_ERROR
                evidence  = ''
                error_msg = str(exc)

        ComplianceResult.objects.create(
            device=device,
            rule=rule,
            status=status,
            evidence=evidence,
            error_message=error_msg,
            task_id=task_id,
        )
        results[status] = results.get(status, 0) + 1

    score = _score(results['pass'], results['pass'] + results['fail'])
    logger.info(
        'compliance %s: pass=%d fail=%d error=%d score=%d%%',
        device.hostname, results['pass'], results['fail'], results['error'], score,
    )
    return {
        'device':  device.hostname,
        'pass':    results['pass'],
        'fail':    results['fail'],
        'error':   results['error'],
        'skipped': results['skipped'],
        'score':   score,
    }


# ── All devices compliance ──────────────────────────────────────────────────────

@shared_task(name='security.run_all_compliance', queue='default')
def run_all_compliance_checks() -> dict:
    """Dispatch compliance checks for every UP device."""
    from apps.inventory.models import Device
    device_ids = list(Device.objects.filter(status='up').values_list('pk', flat=True))
    if not device_ids:
        return {'dispatched': 0}
    job = group(run_compliance_checks.s(did) for did in device_ids)
    result = job.apply_async()
    return {'dispatched': len(device_ids), 'group_id': result.id}


# ── Single device drift check ───────────────────────────────────────────────────

@shared_task(bind=True, name='security.check_drift', queue='default',
             max_retries=1, default_retry_delay=15)
def check_golden_config_drift(self, device_id: int) -> dict:
    """
    Compare `show running-config` against the GoldenConfig for this device's type.
    Creates a DriftResult with unified diff.
    """
    from apps.inventory.models import Device
    from .models import GoldenConfig, DriftResult

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return {'error': 'device_not_found'}

    # Find applicable golden config
    try:
        golden = GoldenConfig.objects.get(device_type=device.device_type, is_active=True)
    except GoldenConfig.DoesNotExist:
        return {'device': device.hostname, 'skipped': True, 'reason': 'no golden config for type'}

    task_id = self.request.id or ''
    running_config = ''

    try:
        running_config = _fetch_running_config(device)
        device.mark_seen()
    except Exception as exc:
        logger.warning('drift fetch failed %s: %s', device.hostname, exc)
        DriftResult.objects.create(
            device=device,
            golden_config=golden,
            status=DriftResult.STATUS_ERROR,
            error_message=str(exc),
            task_id=task_id,
        )
        return {'device': device.hostname, 'error': str(exc)}

    # Normalise — strip trailing whitespace, sort for stable comparison
    golden_lines  = [l.rstrip() for l in golden.content.splitlines() if l.strip()]
    actual_lines  = [l.rstrip() for l in running_config.splitlines() if l.strip()]

    diff_lines = list(difflib.unified_diff(
        golden_lines,
        actual_lines,
        fromfile=f'golden/{device.device_type}',
        tofile=f'running/{device.hostname}',
        lineterm='',
        n=3,
    ))

    changed = sum(1 for l in diff_lines if l.startswith('+') or l.startswith('-'))
    status  = DriftResult.STATUS_CLEAN if changed == 0 else DriftResult.STATUS_DRIFTED

    DriftResult.objects.create(
        device=device,
        golden_config=golden,
        status=status,
        diff='\n'.join(diff_lines),
        drift_lines=changed,
        running_config=running_config[:50_000],
        task_id=task_id,
    )

    logger.info('drift %s: status=%s lines=%d', device.hostname, status, changed)
    return {
        'device':      device.hostname,
        'status':      status,
        'drift_lines': changed,
    }


# ── All devices drift ───────────────────────────────────────────────────────────

@shared_task(name='security.run_all_drift', queue='default')
def run_all_drift_checks() -> dict:
    """Dispatch drift checks for every UP device that has a golden config."""
    from apps.inventory.models import Device
    from .models import GoldenConfig
    typed = set(GoldenConfig.objects.filter(is_active=True).values_list('device_type', flat=True))
    device_ids = list(
        Device.objects.filter(status='up', device_type__in=typed)
        .values_list('pk', flat=True)
    )
    if not device_ids:
        return {'dispatched': 0}
    job = group(check_golden_config_drift.s(did) for did in device_ids)
    result = job.apply_async()
    return {'dispatched': len(device_ids), 'group_id': result.id}
