from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import ConfigTemplate, ProvisioningJob, AuditLog


@login_required
def job_list(request):
    jobs = ProvisioningJob.objects.select_related("template", "initiated_by").order_by("-created_at")[:50]
    return render(request, "provisioning/job_list.html", {"jobs": jobs})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(ProvisioningJob.objects.prefetch_related("results__device", "devices"), pk=pk)
    return render(request, "provisioning/job_detail.html", {"job": job})


@login_required
def template_list(request):
    templates = ConfigTemplate.objects.all().order_by("name")
    return render(request, "provisioning/template_list.html", {"templates": templates})


@login_required
def template_detail(request, pk):
    template = get_object_or_404(ConfigTemplate, pk=pk)
    return render(request, "provisioning/template_detail.html", {"template": template})


@login_required
def audit_log(request):
    logs = AuditLog.objects.select_related("actor", "device").order_by("-timestamp")[:100]
    return render(request, "provisioning/audit_log.html", {"logs": logs})
