from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func=None, *, redirect_url='inventory:dashboard'):
    """Allow only admin role (or superusers). Redirects others."""
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_admin():
                return func(request, *args, **kwargs)
            messages.error(request, 'Administrator access required.')
            return redirect(redirect_url)
        return wrapper
    return decorator(view_func) if view_func else decorator


def engineer_required(view_func=None, *, redirect_url='inventory:dashboard'):
    """Allow admin and engineer roles (or superusers). Redirects read-only users."""
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_engineer():
                return func(request, *args, **kwargs)
            messages.error(request, 'Engineer or Administrator access required.')
            return redirect(redirect_url)
        return wrapper
    return decorator(view_func) if view_func else decorator
