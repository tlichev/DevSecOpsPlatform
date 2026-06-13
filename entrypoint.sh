#!/bin/bash
set -e

echo "Waiting for Redis..."
until redis-cli -u "${REDIS_URL:-redis://redis:6379/0}" ping 2>/dev/null | grep -q PONG; do
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
