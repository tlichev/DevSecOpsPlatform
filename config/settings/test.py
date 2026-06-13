from .base import *  # noqa: F401, F403

SECRET_KEY = 'test-secret-key-ci-only-not-for-production-zx9q3kp4'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# ── In-memory SQLite (no WAL pragmas needed) ──────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# ── In-memory cache (no Redis) ────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ── Celery: run tasks synchronously so tests stay deterministic ───────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_RESULT_BACKEND = 'cache'
CELERY_CACHE_BACKEND = 'default'
CELERY_BROKER_URL = 'memory://'

# ── Fast password hashing (MD5 — test-only, not for production) ───────────────
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# ── No encryption key needed (devices created without ssh_password) ───────────
FIELD_ENCRYPTION_KEY = ''

# ── WhiteNoise: skip manifest compilation in tests ───────────────────────────
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ── Rate limiting — disabled in tests so login tests are not throttled ────────
RATELIMIT_ENABLE = False

# ── Relax security settings ───────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
