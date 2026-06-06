#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; do
  sleep 1
done
echo "==> PostgreSQL ready."

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Creating superuser if missing..."
python manage.py create_superuser_if_missing

echo "==> Seeding compliance rules..."
python manage.py seed_compliance_rules

echo "==> Loading Grafana dashboard fixtures..."
python manage.py loaddata apps/monitoring/fixtures/initial_dashboards.json || true

echo "==> Starting application..."
exec "$@"
