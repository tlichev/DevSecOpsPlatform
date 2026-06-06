import difflib
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="compliance")
def run_compliance_check(self, device_id: int, rule_ids: list[int] = None, initiated_by_id: int = None):
    from .models import ComplianceRule, ComplianceCheck, ComplianceCheck
    from .compliance_checks import evaluate_rule
    from apps.inventory.models import Device
    from apps.provisioning.netmiko_client import NetmikoClient, NetmikoError
    from apps.provisioning.models import AuditLog

    device = Device.objects.get(pk=device_id)
    rules_qs = ComplianceRule.objects.filter(is_active=True)
    if rule_ids:
        rules_qs = rules_qs.filter(pk__in=rule_ids)

    results = []
    for rule in rules_qs:
        try:
            client = NetmikoClient(device)
            output = client.send_command(rule.check_command)
            compliant = evaluate_rule(output, rule.expected_pattern, rule.must_match)
            check_status = ComplianceCheck.Status.COMPLIANT if compliant else ComplianceCheck.Status.NON_COMPLIANT
            detail = "" if compliant else f"Pattern '{rule.expected_pattern}' {'not found' if rule.must_match else 'found (should be absent)'}"
        except NetmikoError as exc:
            output = ""
            check_status = ComplianceCheck.Status.ERROR
            detail = str(exc)
            logger.error("Compliance check error on %s: %s", device.hostname, exc)
        except Exception as exc:
            output = ""
            check_status = ComplianceCheck.Status.ERROR
            detail = f"Unexpected error: {exc}"
            logger.exception("Unexpected error in compliance check on %s", device.hostname)

        check = ComplianceCheck.objects.create(
            device=device,
            rule=rule,
            status=check_status,
            output=output[:4000],
            detail=detail,
            initiated_by_id=initiated_by_id,
        )
        results.append({"rule": rule.name, "status": check_status})

    AuditLog.objects.create(
        action=AuditLog.Action.COMPLIANCE_CHECK,
        actor_id=initiated_by_id,
        device=device,
        success=True,
        detail={"results": results},
    )

    return results


@shared_task(bind=True, queue="compliance")
def run_drift_detection(self, device_id: int, initiated_by_id: int = None):
    from .models import ConfigSnapshot, DriftReport
    from apps.inventory.models import Device
    from apps.provisioning.netmiko_client import NetmikoClient, NetmikoError
    from apps.provisioning.models import AuditLog

    device = Device.objects.get(pk=device_id)

    try:
        client = NetmikoClient(device)
        current_config = client.get_running_config()
    except NetmikoError as exc:
        DriftReport.objects.create(
            device=device,
            status=DriftReport.Status.ERROR,
            diff=str(exc),
        )
        return {"error": str(exc)}

    # Save current snapshot
    current_snap = ConfigSnapshot.objects.create(
        device=device,
        config=current_config,
        taken_by_id=initiated_by_id,
    )

    # Find latest golden snapshot
    golden = ConfigSnapshot.objects.filter(device=device, is_golden=True).order_by("-taken_at").first()

    if not golden:
        logger.info("No golden config for %s; promoting current as golden", device.hostname)
        current_snap.is_golden = True
        current_snap.comment = "Auto-set as initial golden"
        current_snap.save(update_fields=["is_golden", "comment"])
        DriftReport.objects.create(
            device=device,
            golden_snapshot=current_snap,
            current_snapshot=current_snap,
            status=DriftReport.Status.CLEAN,
            diff="",
        )
        return {"status": "clean", "note": "golden config initialized"}

    golden_lines = golden.config.splitlines(keepends=True)
    current_lines = current_config.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        golden_lines, current_lines,
        fromfile=f"golden ({golden.taken_at.date()})",
        tofile=f"current ({current_snap.taken_at.date()})",
        n=3,
    ))

    has_drift = bool(diff_lines)
    diff_text = "".join(diff_lines)

    report = DriftReport.objects.create(
        device=device,
        golden_snapshot=golden,
        current_snapshot=current_snap,
        status=DriftReport.Status.DRIFTED if has_drift else DriftReport.Status.CLEAN,
        diff=diff_text[:10000],
    )

    AuditLog.objects.create(
        action=AuditLog.Action.DRIFT_CHECK,
        actor_id=initiated_by_id,
        device=device,
        success=True,
        detail={"drift": has_drift, "report_id": report.pk},
    )

    return {"status": report.status, "drift": has_drift}


@shared_task(queue="compliance")
def take_config_snapshot(device_id: int, set_golden: bool = False, initiated_by_id: int = None):
    from .models import ConfigSnapshot
    from apps.inventory.models import Device
    from apps.provisioning.netmiko_client import NetmikoClient, NetmikoError
    from apps.provisioning.models import AuditLog

    device = Device.objects.get(pk=device_id)
    try:
        client = NetmikoClient(device)
        config = client.get_running_config()
    except NetmikoError as exc:
        return {"error": str(exc)}

    snap = ConfigSnapshot.objects.create(
        device=device,
        config=config,
        is_golden=set_golden,
        taken_by_id=initiated_by_id,
    )

    AuditLog.objects.create(
        action=AuditLog.Action.SNAPSHOT,
        actor_id=initiated_by_id,
        device=device,
        success=True,
        detail={"snapshot_id": snap.pk, "is_golden": set_golden},
    )

    return {"snapshot_id": snap.pk, "is_golden": set_golden}
