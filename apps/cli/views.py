from django.shortcuts import render, get_object_or_404
from apps.accounts.decorators import engineer_required
from apps.inventory.models import Device
from .models import CLISession


@engineer_required
def console(request, pk):
    device = get_object_or_404(Device, pk=pk)

    # Allow switching between saved sessions via ?session=<id>
    session_id = request.GET.get('session')
    if session_id:
        session = get_object_or_404(CLISession, pk=session_id, device=device)
    else:
        session = CLISession.objects.filter(device=device, user=request.user).first()
        if not session:
            session = CLISession.objects.create(device=device, user=request.user, name='')

    sessions = CLISession.objects.filter(device=device).select_related('user').order_by('-last_used')

    return render(request, 'cli/console.html', {
        'device':   device,
        'session':  session,
        'sessions': sessions,
    })
