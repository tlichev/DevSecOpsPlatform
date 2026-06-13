from .base import *

DEBUG = True
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-only-not-for-production-abc123xyz789')
ALLOWED_HOSTS = ['*']

# ── SQLite database ───────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
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

# ── CORS (allow all in dev) ───────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ── Email (console in dev) ────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Django extensions / debug ─────────────────────────────────────────────────
INTERNAL_IPS = ['127.0.0.1', '0.0.0.0']

# ── Celery (eager mode off — use real workers) ────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = False

# ── Whitenoise dev serving ────────────────────────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ── Security (relaxed for dev) ────────────────────────────────────────────────
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
