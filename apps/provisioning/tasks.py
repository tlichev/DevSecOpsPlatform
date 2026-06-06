import logging
import time
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="provisioning", max_retries=0)
def execute_provisioning_job(self, job_id: int):
    from .models import ProvisioningJob, ProvisioningResult, AuditLog
    from .netmiko_client import NetmikoClient, NetmikoError
    from .jinja_renderer import render_template

    job = ProvisioningJob.objects.select_related("template", "initiated_by").prefetch_related("devices").get(pk=job_id)
    job.status = ProvisioningJob.Status.RUNNING
    job.started_at = datetime.now(tz=timezone.utc)
    job.save(update_fields=["status", "started_at"])

    rendered = render_template(job.template.body, job.variables)
    job.rendered_config = rendered
    job.save(update_fields=["rendered_config"])

    config_lines = [line for line in rendered.splitlines() if line.strip()]
    results = []

    for device in job.devices.all():
        t0 = time.monotonic()
        try:
            client = NetmikoClient(device)
            output = client.push_config(config_lines)
            success = True
            error = ""
            logger.info("Config pushed to %s successfully", device.hostname)
        except NetmikoError as exc:
            output = ""
            error = str(exc)
            success = False
            logger.error("Config push FAILED for %s: %s", device.hostname, exc)
        except Exception as exc:
            output = ""
            error = f"Unexpected error: {exc}"
            success = False
            logger.exception("Unexpected error pushing config to %s", device.hostname)

        duration = time.monotonic() - t0
        result = ProvisioningResult.objects.create(
            job=job,
            device=device,
            success=success,
            output=output,
            error=error,
            duration_seconds=round(duration, 2),
        )
        results.append(result)

        AuditLog.objects.create(
            action=AuditLog.Action.PUSH_CONFIG,
            actor=job.initiated_by,
            device=device,
            success=success,
            detail={
                "job_id": job.pk,
                "template": job.template.name if job.template else "ad-hoc",
                "variables": job.variables,
                "error": error,
                "duration_seconds": round(duration, 2),
            },
        )

    total = len(results)
    successes = sum(1 for r in results if r.success)

    if successes == total:
        job.status = ProvisioningJob.Status.SUCCESS
    elif successes == 0:
        job.status = ProvisioningJob.Status.FAILED
    else:
        job.status = ProvisioningJob.Status.PARTIAL

    job.completed_at = datetime.now(tz=timezone.utc)
    job.save(update_fields=["status", "completed_at"])

    return {"job_id": job_id, "total": total, "success": successes, "failed": total - successes}
