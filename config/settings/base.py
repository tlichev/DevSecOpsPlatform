import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-base-change-me')
DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# ── Apps ──────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_filters',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.inventory',
    'apps.provisioning',
    'apps.monitoring',
    'apps.security',
    'apps.cli',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ── i18n ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Sofia'
USE_I18N = True
USE_TZ = True

# ── Static & media ────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ── API docs ──────────────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'NetOps Platform API',
    'DESCRIPTION': 'DevSecOps Network Infrastructure Automation Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'default'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Sofia'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600

CELERY_TASK_ROUTES = {
    'apps.inventory.tasks.*': {'queue': 'discovery'},
    'apps.provisioning.tasks.*': {'queue': 'provisioning'},
    'apps.monitoring.tasks.*': {'queue': 'monitoring'},
    'apps.security.tasks.*': {'queue': 'default'},
}

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    # Poll all devices every 5 minutes
    'poll-all-devices': {
        'task': 'inventory.poll_all_devices',
        'schedule': 300.0,
        'options': {'queue': 'monitoring'},
    },
    # Sync Prometheus alerts every 2 minutes (reconciliation fallback)
    'sync-prometheus-alerts': {
        'task': 'monitoring.sync_alerts',
        'schedule': 120.0,
        'options': {'queue': 'monitoring'},
    },
    # Update device status from active DeviceDown alerts every 3 minutes
    'mark-devices-from-alerts': {
        'task': 'monitoring.mark_devices_from_alerts',
        'schedule': 180.0,
        'options': {'queue': 'monitoring'},
    },
    # Run compliance checks daily at 02:00 EET
    'daily-compliance-check': {
        'task': 'security.run_all_compliance',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'default'},
    },
    # Run drift detection daily at 03:00 EET
    'daily-drift-check': {
        'task': 'security.run_all_drift',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'default'},
    },
}

# ── External services ─────────────────────────────────────────────────────────
GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://grafana:3000')
# URL accessible from the user's browser (for iframes); differs from internal Docker URL
GRAFANA_BROWSER_URL = os.environ.get('GRAFANA_BROWSER_URL', 'http://localhost:3000')
GRAFANA_API_TOKEN = os.environ.get('GRAFANA_API_TOKEN', '')
ALERTMANAGER_URL = os.environ.get('ALERTMANAGER_URL', 'http://alertmanager:9093')
SNMP_DEFAULT_COMMUNITY = os.environ.get('SNMP_DEFAULT_COMMUNITY', 'public')
MGMT_NETWORK = os.environ.get('MGMT_NETWORK', '192.168.100.0/24')

# Fernet key for encrypting device SSH passwords at rest
FIELD_ENCRYPTION_KEY = os.environ.get('FIELD_ENCRYPTION_KEY', '')

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.db.backends': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
