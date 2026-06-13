from django.db.backends.signals import connection_created


def _set_sqlite_pragmas(sender, connection, **kwargs):
    """
    Apply WAL journal mode and performance/safety PRAGMAs every time
    a new SQLite connection is opened. This is the correct way to set
    PRAGMAs in Django — init_command is MySQL-only and invalid for SQLite.
    """
    if connection.vendor != 'sqlite':
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA cache_size=-64000')   # 64 MB page cache
        cursor.execute('PRAGMA temp_store=MEMORY')


connection_created.connect(_set_sqlite_pragmas)
