import time
import difflib
import logging

from celery import shared_task, group
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Single device push ─────────────────────────────────────────────────────────
@shared_task(bind=True, name='provisioning.push_config', queue='provisioning',
             max_retries=1, default_retry_delay=10)
def push_config_to_device(self, device_id: int, template_name: str,
                           extra_context: dict | None = None,
                           user_id: int | None = None,
                           dry_run: bool = False) -> dict:
    """
    Render a Jinja2 config template and push it to one device via Netmiko.
    Creates / updates an AuditLog entry.
    """
    from apps.inventory.models import Device
    from .models import AuditLog
    from .template_engine import render_template

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return {'error': 'device_not_found', 'device_id': device_id}

    user = None
    if user_id:
        try:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(pk=user_id)
        except Exception:
            pass

    # Render the template
    try:
        rendered = render_template(template_name, device, extra_context or {})
    except Exception as exc:
        logger.error('Template render failed for %s/%s: %s', device.hostname, template_name, exc)
        AuditLog.objects.create(
            device=device, user=user,
            template_name=template_name,
            action=f'Push {template_name}',
            status=AuditLog.STATUS_FAILED,
            error_message=f'Template render error: {exc}',
            task_id=self.request.id or '',
        )
        return {'error': str(exc), 'device': device.hostname}

    audit = AuditLog(
        device=device, user=user,
        template_name=template_name,
        action=f'{"DRY RUN " if dry_run else ""}Push {template_name}',
        config_sent=rendered,
        task_id=self.request.id or '',
    )

    if dry_run:
        audit.status = AuditLog.STATUS_SUCCESS
        audit.config_diff = '(dry-run — no changes applied)'
        audit.execution_time = 0
        audit.save()
        return {'device': device.hostname, 'status': 'dry_run', 'rendered': rendered}

    start = time.perf_counter()
    try:
        from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

        params = device.get_netmiko_params()

        with ConnectHandler(**params) as conn:
            # Capture before-config for diff
            before = conn.send_command('show running-config', read_timeout=60)

            # Send config commands line by line
            commands = [
                line for line in rendered.splitlines()
                if line.strip() and not line.strip().startswith('!')
            ]
            output = conn.send_config_set(commands, read_timeout=120)
            conn.save_config()

            # Capture after-config for diff
            after = conn.send_command('show running-config', read_timeout=60)

        diff_lines = list(difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile='running-config (before)',
            tofile='running-config (after)',
            lineterm='',
            n=3,
        ))
        audit.config_diff = '\n'.join(diff_lines)
        audit.status = AuditLog.STATUS_SUCCESS

        # Mark device as seen (it responded)
        device.mark_seen()

    except Exception as exc:
        logger.error('Netmiko push failed %s → %s: %s', template_name, device.hostname, exc)
        audit.status = AuditLog.STATUS_FAILED
        audit.error_message = str(exc)
        # Don't retry auth failures
        from netmiko import NetmikoAuthenticationException
        if isinstance(exc, NetmikoAuthenticationException):
            audit.save()
            return {'device': device.hostname, 'status': 'auth_failed', 'error': str(exc)}
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            pass

    finally:
        audit.execution_time = time.perf_counter() - start
        audit.save()

    return {
        'device':        device.hostname,
        'status':        audit.status,
        'duration':      audit.execution_time,
        'audit_log_id':  audit.pk,
    }


# ── Multi-device push ──────────────────────────────────────────────────────────
@shared_task(name='provisioning.push_config_multi', queue='provisioning')
def push_config_to_devices(device_ids: list[int], template_name: str,
                            extra_context: dict | None = None,
                            user_id: int | None = None,
                            dry_run: bool = False) -> dict:
    """Dispatch concurrent per-device push tasks and return task IDs."""
    job = group(
        push_config_to_device.s(
            device_id, template_name, extra_context or {}, user_id, dry_run
        )
        for device_id in device_ids
    )
    result = job.apply_async()
    return {
        'group_id': result.id,
        'device_count': len(device_ids),
        'template': template_name,
        'dry_run': dry_run,
    }


# ── Render preview (no push) ───────────────────────────────────────────────────
@shared_task(name='provisioning.render_preview', queue='default')
def render_preview(device_id: int, template_name: str,
                   extra_context: dict | None = None) -> dict:
    """Render a template for a device and return the result without pushing."""
    from apps.inventory.models import Device
    from .template_engine import render_template

    try:
        device = Device.objects.get(pk=device_id)
        rendered = render_template(template_name, device, extra_context or {})
        return {'rendered': rendered, 'device': device.hostname, 'template': template_name}
    except Exception as exc:
        return {'error': str(exc)}
