from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count

from apps.accounts.decorators import engineer_required
from .models import Device
from .forms import DeviceForm


@login_required
def dashboard(request):
    return render(request, 'dashboard.html')


@login_required
def device_list(request):
    qs = Device.objects.all()

    site_filter   = request.GET.get('site', '').strip()
    type_filter   = request.GET.get('device_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    search_query  = request.GET.get('q', '').strip()

    if site_filter:
        qs = qs.filter(site=site_filter)
    if type_filter:
        qs = qs.filter(device_type=type_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if search_query:
        qs = qs.filter(
            Q(hostname__icontains=search_query) |
            Q(ip_address__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(model__icontains=search_query)
        )

    devices = qs.order_by('site', 'hostname')

    counts = {
        'total':   Device.objects.count(),
        'up':      Device.objects.filter(status=Device.STATUS_UP).count(),
        'down':    Device.objects.filter(status=Device.STATUS_DOWN).count(),
        'unknown': Device.objects.filter(status=Device.STATUS_UNKNOWN).count(),
    }

    return render(request, 'inventory/device_list.html', {
        'devices':        devices,
        'counts':         counts,
        'site_filter':    site_filter,
        'type_filter':    type_filter,
        'status_filter':  status_filter,
        'search_query':   search_query,
        'site_choices':   Device.SITE_CHOICES,
        'type_choices':   Device.DEVICE_TYPE_CHOICES,
        'status_choices': Device.STATUS_CHOICES,
        'filtered_count': devices.count(),
    })


@login_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    # Try to pull recent provisioning events — model exists after Step 4
    recent_events = []
    try:
        from apps.provisioning.models import AuditLog
        recent_events = AuditLog.objects.filter(device=device).order_by('-timestamp')[:10]
    except Exception:
        pass

    return render(request, 'inventory/device_detail.html', {
        'device':        device,
        'recent_events': recent_events,
    })


@engineer_required
def device_create(request):
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save()
            messages.success(request, f'Device {device.hostname} added to inventory.')
            return redirect('inventory:device_detail', pk=device.pk)
    else:
        form = DeviceForm()
    return render(request, 'inventory/device_form.html', {
        'form': form,
        'title': 'Add Device',
        'action': 'Add Device',
    })


@engineer_required
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, f'{device.hostname} updated successfully.')
            return redirect('inventory:device_detail', pk=device.pk)
    else:
        form = DeviceForm(instance=device)
    return render(request, 'inventory/device_form.html', {
        'form': form,
        'device': device,
        'title': f'Edit {device.hostname}',
        'action': 'Save Changes',
    })


@engineer_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == 'POST':
        hostname = device.hostname
        device.delete()
        messages.success(request, f'Device {hostname} removed from inventory.')
        return redirect('inventory:device_list')
    return redirect('inventory:device_detail', pk=pk)


@login_required
def site_sofia(request):
    devices = Device.objects.filter(site=Device.SITE_SOFIA).order_by('device_type', 'hostname')
    return render(request, 'sites/sofia.html', {'devices': devices})


@login_required
def site_burgas(request):
    devices = Device.objects.filter(site=Device.SITE_BURGAS).order_by('device_type', 'hostname')
    return render(request, 'sites/burgas.html', {'devices': devices})


@login_required
def site_plovdiv(request):
    devices = Device.objects.filter(site=Device.SITE_PLOVDIV).order_by('device_type', 'hostname')
    return render(request, 'sites/plovdiv.html', {'devices': devices})
