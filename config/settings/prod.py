import os
from .base import *  # noqa: F401, F403

# ── Core ──────────────────────────────────────────────────────────────────────
DEBUG = False

# Raise immediately if SECRET_KEY is not explicitly provided — no insecure fallback
SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# ── Database (SQLite WAL — production-tuned) ──────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
            'init_command': (
                'PRAGMA journal_mode=WAL;'
                'PRAGMA synchronous=NORMAL;'
                'PRAGMA foreign_keys=ON;'
                'PRAGMA cache_size=-64000;'  # 64 MB page cache
                'PRAGMA temp_store=MEMORY;'
            ),
        },
    }
}

# ── Cache (Redis) ─────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/1'),
    }
}

# ── Middleware (CSP injected after SecurityMiddleware) ────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ── HTTPS / Transport security ────────────────────────────────────────────────
# When running behind an nginx/traefik reverse proxy that terminates TLS:
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ── Session & CSRF cookies ─────────────────────────────────────────────────────
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28_800               # 8 hours

CSRF_COOKIE_SECURE = True
# Must remain JS-readable so fetch() calls can extract the token:
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'

# ── Clickjacking — allow same-origin iframes (Grafana embed is same host) ─────
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ── Content Security Policy ───────────────────────────────────────────────────
# Grafana iframes need frame-src; value comes from env so it works with
# any hostname or port the operator exposes Grafana on.
_grafana_origin = os.environ.get('GRAFANA_BROWSER_URL', 'http://localhost:3000')

CSP_DEFAULT_SRC  = ("'self'",)
# Inline scripts are used extensively in templates (chart init, AJAX polling).
# Tighten to nonce-only in a future iteration after templates are refactored.
CSP_SCRIPT_SRC   = ("'self'", "'unsafe-inline'")
CSP_STYLE_SRC    = (
    "'self'", "'unsafe-inline'",
    'https://fonts.googleapis.com',
    'https://cdn.jsdelivr.net',          # Bootstrap 5 CDN
)
CSP_FONT_SRC     = (
    "'self'",
    'https://fonts.gstatic.com',
    'https://cdn.jsdelivr.net',
)
CSP_IMG_SRC      = ("'self'", 'data:', 'blob:')
# Allow Grafana iframes; only same-origin otherwise
CSP_FRAME_SRC    = ("'self'", _grafana_origin)
# XHR / fetch() only to self (AJAX calls go to /api/*)
CSP_CONNECT_SRC  = ("'self'",)
CSP_OBJECT_SRC   = ("'none'",)
CSP_BASE_URI     = ("'self'",)
CSP_FORM_ACTION  = ("'self'",)
# Prevent this app from being framed by third-party sites
CSP_FRAME_ANCESTORS = ("'self'",)
# Report-only mode: flip to CSP_REPORT_ONLY = True during rollout to catch violations before enforcing
CSP_REPORT_ONLY  = False

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ── Rate limiting (django-ratelimit) ─────────────────────────────────────────
# Uses the 'default' Redis cache; keys expire naturally.
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True

# ── Email (SMTP) ──────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'noreply@netops-platform.local'
)

# ── Static files ──────────────────────────────────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'prod': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'prod',
        },
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django':              {'handlers': ['console'], 'level': 'WARNING',  'propagate': False},
        'django.security':     {'handlers': ['console'], 'level': 'ERROR',    'propagate': False},
        'django.request':      {'handlers': ['console'], 'level': 'ERROR',    'propagate': False},
        'apps':                {'handlers': ['console'], 'level': 'INFO',     'propagate': False},
        'celery':              {'handlers': ['console'], 'level': 'WARNING',  'propagate': False},
    },
}
