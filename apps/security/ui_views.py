from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import ComplianceCheck, DriftReport


@login_required
def compliance_dashboard(request):
    total = ComplianceCheck.objects.count()
    compliant = ComplianceCheck.objects.filter(status="compliant").count()
    non_compliant = ComplianceCheck.objects.filter(status="non_compliant").count()
    recent_checks = ComplianceCheck.objects.select_related("device", "rule").order_by("-checked_at")[:20]
    recent_drifts = DriftReport.objects.filter(status="drifted").select_related("device").order_by("-checked_at")[:10]
    return render(request, "security/compliance_dashboard.html", {
        "total": total,
        "compliant": compliant,
        "non_compliant": non_compliant,
        "recent_checks": recent_checks,
        "recent_drifts": recent_drifts,
    })


@login_required
def compliance_checks(request):
    checks = ComplianceCheck.objects.select_related("device", "rule").order_by("-checked_at")[:200]
    return render(request, "security/compliance_checks.html", {"checks": checks})


@login_required
def drift_reports(request):
    reports = DriftReport.objects.select_related("device").order_by("-checked_at")[:100]
    return render(request, "security/drift_reports.html", {"reports": reports})


@login_required
def drift_detail(request, pk):
    report = get_object_or_404(DriftReport.objects.select_related("device", "golden_snapshot", "current_snapshot"), pk=pk)
    return render(request, "security/drift_detail.html", {"report": report})
