# Django Core (`devsecops_platform/`)

The `devsecops_platform` package is the Django project root. It wires together all apps, configures all third-party libraries, defines the URL structure, and applies security middleware.

---

## File Structure

```
devsecops_platform/
├── __init__.py            # Imports Celery app so it loads with Django
├── settings.py            # All configuration (environment-driven)
├── urls.py                # Root URL router
├── celery.py              # Celery application definition
├── middleware.py          # SecurityHeadersMiddleware
├── context_processors.py  # Template globals (GRAFANA_URL, PLATFORM_NAME)
└── wsgi.py                # WSGI entrypoint for Gunicorn
```

---

## `settings.py`

All settings are driven by environment variables via `django-environ`. The `.env` file is read at startup. No secrets are hardcoded.

### Key sections

#### Installed apps
```python
INSTALLED_APPS = [
    # Django built-ins...
    "whitenoise.runserver_nostatic",  # Static file serving
    "rest_framework",                  # DRF
    "rest_framework_simplejwt",        # JWT auth
    "rest_framework_simplejwt.token_blacklist",  # Refresh token invalidation
    "corsheaders",                     # CORS headers
    "django_filters",                  # URL-based queryset filtering
    "django_celery_results",           # Store Celery results in DB
    "django_celery_beat",              # Periodic task scheduling via DB
    "apps.inventory",
    "apps.provisioning",
    "apps.monitoring",
    "apps.security",
]
```

#### REST Framework
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",    # Unauthenticated API callers
        "user": "300/minute",   # Authenticated users
    },
    "PAGE_SIZE": 25,
}
```

#### JWT
```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,       # Issue new refresh token on each refresh
    "BLACKLIST_AFTER_ROTATION": True,    # Invalidate old refresh token
    "ALGORITHM": "HS256",
}
```

#### Celery
```python
CELERY_TASK_ROUTES = {
    "apps.provisioning.tasks.*": {"queue": "provisioning"},
    "apps.inventory.tasks.*":    {"queue": "discovery"},
    "apps.security.tasks.*":     {"queue": "compliance"},
}
```

Tasks are explicitly routed to named queues. The Celery worker must be started with all queues:
```
celery -A devsecops_platform worker -l info -Q default,provisioning,discovery,compliance
```

#### Security hardening (production)

When `DJANGO_DEBUG=False`, these are automatically activated:

| Setting | Value | Effect |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` | HTTP → HTTPS redirect |
| `SECURE_HSTS_SECONDS` | `31536000` | 1-year HSTS header |
| `SESSION_COOKIE_SECURE` | `True` | Session cookie only over HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | CSRF cookie only over HTTPS |
| `X_FRAME_OPTIONS` | `SAMEORIGIN` | Allows Grafana iframes on same origin |

---

## `celery.py`

```python
app = Celery("devsecops_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

`autodiscover_tasks()` finds `tasks.py` in every installed app automatically. No manual task registration needed.

The `__init__.py` import ensures the Celery app loads when Django starts, even if no Celery-specific code is called:
```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

---

## `middleware.py` — Security Headers

`SecurityHeadersMiddleware` adds HTTP response headers on every request:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Allow Grafana iframes on same origin |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable unused browser APIs |
| `Content-Security-Policy` | (see below) | Restrict resource origins |

**CSP policy:**
```
default-src 'self';
script-src  'self' 'unsafe-inline' cdn.jsdelivr.net;
style-src   'self' 'unsafe-inline' cdn.jsdelivr.net;
img-src     'self' data:;
frame-src   'self' http://localhost:3000 http://grafana:3000;
connect-src 'self';
```

`frame-src` allows both localhost:3000 (development) and the internal Docker hostname `grafana:3000`.

---

## `urls.py` — URL Structure

```
/                           → redirect to /dashboard/
/admin/                     → Django admin

/api/auth/token/            → POST: obtain JWT pair
/api/auth/token/refresh/    → POST: refresh access token
/api/auth/token/verify/     → POST: verify access token

/api/inventory/             → Inventory API (devices, discovery)
/api/provisioning/          → Provisioning API (templates, jobs, audit)
/api/monitoring/            → Monitoring API (alerts, dashboards, webhook)
/api/security/              → Security API (rules, checks, snapshots, drift, users)

/dashboard/                 → Main monitoring dashboard
/inventory/                 → Device list and detail pages
/provisioning/              → Job list, template list, audit log
/security/                  → Compliance dashboard and drift reports
```

---

## `context_processors.py`

Makes these variables available in every Django template without explicit passing:

| Variable | Source | Used for |
|---|---|---|
| `GRAFANA_URL` | `settings.GRAFANA_URL` | iframe `src` base URL |
| `PROMETHEUS_URL` | `settings.PROMETHEUS_URL` | Links to Prometheus |
| `PLATFORM_NAME` | Hardcoded `"DevSecOps Platform"` | Page titles |

---

## Environment Variables Reference

All variables are consumed in `settings.py`. Set them in `.env`.

| Variable | Type | Required | Default | Description |
|---|---|---|---|---|
| `DJANGO_SECRET_KEY` | str | Yes | — | 50+ char random string |
| `DJANGO_DEBUG` | bool | No | `False` | Enable debug mode |
| `DJANGO_ALLOWED_HOSTS` | list | Yes | — | Comma-separated hostnames |
| `POSTGRES_DB` | str | Yes | — | Database name |
| `POSTGRES_USER` | str | Yes | — | Database user |
| `POSTGRES_PASSWORD` | str | Yes | — | Database password |
| `POSTGRES_HOST` | str | Yes | — | Database host |
| `POSTGRES_PORT` | int | No | `5432` | Database port |
| `CELERY_BROKER_URL` | str | Yes | — | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | str | Yes | — | Redis URL for results |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | int | No | `60` | JWT access token TTL |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | int | No | `7` | JWT refresh token TTL |
| `GRAFANA_URL` | str | No | `http://localhost:3000` | Browser-facing Grafana URL |
| `GRAFANA_INTERNAL_URL` | str | No | `=GRAFANA_URL` | Docker-internal Grafana URL |
| `GRAFANA_ADMIN_USER` | str | No | `admin` | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | str | No | `admin` | Grafana admin password |
| `PROMETHEUS_URL` | str | No | `http://localhost:9090` | Prometheus URL |
| `ALERTMANAGER_URL` | str | No | `http://localhost:9093` | AlertManager URL |
| `MANAGEMENT_SUBNET` | str | No | `192.168.100.0/24` | EVE-NG management subnet |
| `SNMP_COMMUNITY` | str | No | `public` | Default SNMP community |
| `DJANGO_SUPERUSER_USERNAME` | str | No | `admin` | Auto-created superuser name |
| `DJANGO_SUPERUSER_PASSWORD` | str | No | `adminpassword123` | Auto-created superuser password |
