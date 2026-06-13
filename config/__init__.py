from .celery import app as celery_app
from . import db_pragmas  # noqa: F401 — registers SQLite WAL signal on import

__all__ = ('celery_app',)
