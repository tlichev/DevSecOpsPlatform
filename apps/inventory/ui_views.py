from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import Device, DiscoveryJob


@login_required
def device_list(request):
    devices = Device.objects.all().order_by("hostname")
    return render(request, "inventory/device_list.html", {"devices": devices})


@login_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return render(request, "inventory/device_detail.html", {"device": device})


@login_required
def device_add(request):
    return render(request, "inventory/device_add.html", {})


@login_required
def discovery_list(request):
    jobs = DiscoveryJob.objects.select_related("initiated_by").order_by("-created_at")[:20]
    return render(request, "inventory/discovery_list.html", {"jobs": jobs})
