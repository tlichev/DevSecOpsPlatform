#!/bin/bash
set -e

echo "Waiting for Redis..."
until python -c "
import sys, os
try:
    import redis
    r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
    r.ping()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    sleep 1
done
echo "Redis is ready."

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

if [ "$LOAD_FIXTURES" = "1" ]; then
    python manage.py loaddata fixtures/devices.json || true
    python manage.py loaddata fixtures/compliance_rules.json || true
fi

exec "$@"
