from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from .forms import ProfileUpdateForm, CustomPasswordChangeForm, AdminUserRoleForm
from .decorators import admin_required
from .models import TwoFactorCode

User = get_user_model()

MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def login_view(request):
    logger.debug('login_view: method=%s authenticated=%s', request.method, request.user.is_authenticated)

    if request.user.is_authenticated:
        logger.debug('login_view: already authenticated, redirecting to dashboard')
        return redirect('inventory:dashboard')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            return HttpResponseForbidden(
                'Too many login attempts. Please wait a minute and try again.'
            )
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        logger.debug('login_view: POST attempt for username=%s', username)

        user = authenticate(request, username=username, password=password)
        logger.debug('login_view: authenticate() returned %s', user)

        if user is not None:
            logger.debug('login_view: user email=%s', repr(user.email))
            if not user.email:
                logger.debug('login_view: no email — skipping 2FA, logging in directly')
                login(request, user)
                return redirect(request.GET.get('next', '/'))

            # Generate OTP and store pre-auth state in session
            logger.debug('login_view: generating OTP for user %s', user.pk)
            otp = TwoFactorCode.generate_for(user)
            logger.debug('login_view: OTP created pk=%s code=%s', otp.pk, otp.code)

            request.session['pre_auth_user_id'] = user.pk
            request.session['pre_auth_backend'] = user.backend
            request.session['pre_auth_next'] = request.GET.get('next', '/')
            request.session['pre_auth_attempts'] = 0
            request.session['pre_auth_resend_at'] = None

            from .tasks import send_otp_email
            send_otp_email.apply_async((user.pk, otp.code), queue='default')
            logger.debug('login_view: OTP email queued, redirecting to verify-otp')

            return redirect('accounts:verify_otp')

        logger.debug('login_view: authenticate() failed')
        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    # Clear any leftover pre-auth session keys
    for key in ('pre_auth_user_id', 'pre_auth_backend', 'pre_auth_next',
                 'pre_auth_attempts', 'pre_auth_resend_at'):
        request.session.pop(key, None)
    logout(request)
    return redirect('accounts:login')


@ratelimit(key='ip', rate='20/m', method='POST', block=False)
def verify_otp_view(request):
    user_id = request.session.get('pre_auth_user_id')
    if not user_id:
        return redirect('accounts:login')

    if getattr(request, 'limited', False):
        messages.error(request, 'Too many verification attempts. Please log in again.')
        _clear_pre_auth(request)
        return redirect('accounts:login')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _clear_pre_auth(request)
        return redirect('accounts:login')

    masked_email = _mask_email(user.email)

    if request.method == 'POST':
        entered = request.POST.get('code', '').strip()
        attempts = request.session.get('pre_auth_attempts', 0) + 1
        request.session['pre_auth_attempts'] = attempts

        if attempts > MAX_OTP_ATTEMPTS:
            messages.error(request, 'Too many incorrect attempts. Please log in again.')
            _clear_pre_auth(request)
            return redirect('accounts:login')

        try:
            otp = TwoFactorCode.objects.get(user=user, code=entered, used=False)
        except TwoFactorCode.DoesNotExist:
            remaining = MAX_OTP_ATTEMPTS - attempts
            if remaining > 0:
                messages.error(
                    request,
                    f'Invalid code. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
                )
            return render(request, 'accounts/verify_otp.html', {
                'masked_email': masked_email,
                'attempts_left': remaining,
            })

        if not otp.is_valid():
            messages.error(request, 'This code has expired. Please log in again.')
            _clear_pre_auth(request)
            return redirect('accounts:login')

        # Valid — complete the login
        otp.used = True
        otp.save(update_fields=['used'])
        TwoFactorCode.objects.filter(user=user).delete()

        user.backend = request.session.get(
            'pre_auth_backend', 'django.contrib.auth.backends.ModelBackend'
        )
        next_url = request.session.get('pre_auth_next', '/')
        _clear_pre_auth(request)
        login(request, user)
        return redirect(next_url)

    return render(request, 'accounts/verify_otp.html', {
        'masked_email': masked_email,
        'attempts_left': MAX_OTP_ATTEMPTS,
    })


def resend_otp_view(request):
    """POST only — regenerate and resend the OTP for the current pre-auth session."""
    if request.method != 'POST':
        return redirect('accounts:verify_otp')

    user_id = request.session.get('pre_auth_user_id')
    if not user_id:
        return redirect('accounts:login')

    # Enforce resend cooldown
    resend_at = request.session.get('pre_auth_resend_at')
    if resend_at:
        from datetime import datetime
        last_sent = datetime.fromisoformat(resend_at)
        elapsed = (timezone.now().replace(tzinfo=None) - last_sent).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait = int(RESEND_COOLDOWN_SECONDS - elapsed)
            messages.error(request, f'Please wait {wait} seconds before requesting a new code.')
            return redirect('accounts:verify_otp')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _clear_pre_auth(request)
        return redirect('accounts:login')

    otp = TwoFactorCode.generate_for(user)
    request.session['pre_auth_attempts'] = 0
    request.session['pre_auth_resend_at'] = timezone.now().replace(tzinfo=None).isoformat()

    from .tasks import send_otp_email
    send_otp_email.apply_async((user.pk, otp.code), queue='default')

    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('accounts:verify_otp')


# ── Authenticated views ──────────────────────────────────────────────────────

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
        ('Administrators', 'danger',    users.filter(role=User.ROLE_ADMIN).count()),
        ('Engineers',      'primary',   users.filter(role=User.ROLE_ENGINEER).count()),
        ('Read-Only',      'secondary', users.filter(role=User.ROLE_READONLY).count()),
    ]
    return render(request, 'accounts/users.html', {
        'users':        users,
        'role_stats':   role_stats,
        'role_choices': User.ROLE_CHOICES,
    })


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_pre_auth(request):
    for key in ('pre_auth_user_id', 'pre_auth_backend', 'pre_auth_next',
                 'pre_auth_attempts', 'pre_auth_resend_at'):
        request.session.pop(key, None)


def _mask_email(email: str) -> str:
    """Return t***@gmail.com style masked address."""
    if not email or '@' not in email:
        return '***'
    local, domain = email.split('@', 1)
    visible = local[0] if local else '*'
    return f'{visible}***@{domain}'
