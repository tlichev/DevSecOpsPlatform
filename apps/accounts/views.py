from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from django_ratelimit.decorators import ratelimit

from .forms import ProfileUpdateForm, CustomPasswordChangeForm, AdminUserRoleForm
from .decorators import admin_required

User = get_user_model()


@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')

    if request.method == 'POST':
        # django-ratelimit sets request.limited=True when threshold exceeded
        if getattr(request, 'limited', False):
            return HttpResponseForbidden(
                'Too many login attempts. Please wait a minute and try again.'
            )
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    try:
        from apps.provisioning.models import AuditLog
        audit_count = AuditLog.objects.filter(triggered_by=request.user).count()
    except Exception:
        audit_count = 0

    return render(request, 'accounts/profile.html', {
        'form': form,
        'audit_count': audit_count,
    })


@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:profile')
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


@admin_required
def user_list_view(request):
    users = User.objects.all().order_by('username')
    role_stats = [
        ('Administrators', 'danger', users.filter(role=User.ROLE_ADMIN).count()),
        ('Engineers',      'primary', users.filter(role=User.ROLE_ENGINEER).count()),
        ('Read-Only',      'secondary', users.filter(role=User.ROLE_READONLY).count()),
    ]
    return render(request, 'accounts/users.html', {
        'users': users,
        'role_stats': role_stats,
        'role_choices': User.ROLE_CHOICES,
    })
