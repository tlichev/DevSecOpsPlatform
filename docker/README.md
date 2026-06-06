# Docker (`docker/`)

The `docker/` directory contains the container entrypoint script. The `Dockerfile` and `docker-compose.yml` are in the project root.

---

## File Structure

```
docker/
└── entrypoint.sh    # Container startup script
```

---

## `entrypoint.sh` — Container Startup Script

Runs every time the Django container starts, before the actual application process. It performs all one-time setup steps that must complete before the app can serve requests.

### Sequence of operations

```
1. Wait for PostgreSQL to be ready
2. Run Django database migrations
3. Collect static files
4. Create superuser (if it doesn't exist)
5. Seed compliance rules (idempotent)
6. Load Grafana dashboard fixtures (idempotent)
7. exec "$@"  ← hand off to the CMD from docker-compose.yml
```

### Step-by-step breakdown

#### 1. Wait for PostgreSQL

```sh
until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; do
  sleep 1
done
```

Polls `pg_isready` in a loop until PostgreSQL accepts connections. This handles the race condition between the Django container starting and PostgreSQL finishing its initialization. The `pg_isready` command is provided by the `postgresql-client` package installed in the Dockerfile.

Without this wait, `migrate` would fail with "connection refused" if Django starts before Postgres is ready.

#### 2. Database migrations

```sh
python manage.py migrate --noinput
```

Applies all pending Django migrations. `--noinput` prevents interactive prompts that would hang the container.

Safe to run on an already-migrated database — Django tracks applied migrations in the `django_migrations` table.

#### 3. Static files

```sh
python manage.py collectstatic --noinput
```

Copies all static files (CSS, JS, images) from each app's `static/` directory into `STATIC_ROOT`. WhiteNoise serves them from there.

Only needed because `DEBUG=False` in production — in production, Django does not serve static files itself.

#### 4. Create superuser

```sh
python manage.py create_superuser_if_missing
```

A custom management command (idempotent — does nothing if the superuser already exists). Creates the admin account using:
- `DJANGO_SUPERUSER_USERNAME` — default: `admin`
- `DJANGO_SUPERUSER_EMAIL` — default: `admin@localhost`
- `DJANGO_SUPERUSER_PASSWORD` — default: `adminpassword123`

Change these in `.env` before first deployment.

#### 5. Seed compliance rules

```sh
python manage.py seed_compliance_rules
```

Creates the 8 built-in compliance rules using `update_or_create`. Safe to run multiple times — existing rules are updated, not duplicated.

#### 6. Load Grafana dashboard fixtures

```sh
python manage.py loaddata apps/monitoring/fixtures/initial_dashboards.json || true
```

Loads the 3 `GrafanaDashboard` records (network-overview, node-exporter-full, alertmanager-alerts) into the database. The `|| true` means failure is non-fatal — if the fixture was already loaded, Django raises an `IntegrityError` on the unique `uid` field, and we skip it.

#### 7. Execute the application

```sh
exec "$@"
```

Replaces the shell process with whatever command was passed to the container (the `CMD` from `docker-compose.yml`). This ensures:
- The application process becomes PID 1 (receives signals directly)
- `SIGTERM` from `docker compose stop` reaches Gunicorn cleanly for graceful shutdown

---

## `Dockerfile`

Located at the project root. Key design decisions:

### Base image

```dockerfile
FROM python:3.11-slim
```

Slim variant — no unnecessary packages. ~150MB smaller than the full Python image.

### System packages

```dockerfile
RUN apt-get install -y --no-install-recommends \
    gcc libpq-dev postgresql-client \
    iputils-ping nmap openssh-client snmp
```

| Package | Why |
|---|---|
| `gcc` | Compile Python extensions (psycopg2) |
| `libpq-dev` | PostgreSQL client headers (psycopg2 build) |
| `postgresql-client` | Provides `pg_isready` for entrypoint.sh |
| `iputils-ping` | `ping` command for device reachability checks |
| `nmap` | Port scanning during network discovery |
| `openssh-client` | SSH client for Netmiko connections |
| `snmp` | `snmpwalk`/`snmpget` for manual SNMP debugging |

### Non-root user

```dockerfile
RUN useradd --create-home --shell /bin/bash django
USER django
```

The container runs as the `django` user (non-root). If a container escape vulnerability is exploited, the attacker gets a limited user, not root.

### Entrypoint vs CMD

```dockerfile
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "devsecops_platform.wsgi:application", ...]
```

- `ENTRYPOINT` — always runs; performs setup
- `CMD` — the default command; can be overridden in `docker-compose.yml`

For the Celery worker, `docker-compose.yml` overrides `CMD`:
```yaml
command: celery -A devsecops_platform worker -l info -Q default,provisioning,discovery,compliance
```

The entrypoint still runs first (migrations, etc.) before Celery starts. This is intentional — the worker needs the database to exist.

---

## `docker-compose.yml` — Service Architecture

Located at project root. Defines 10 services across 3 networks.

### Services

| Service | Image | Port | Role |
|---|---|---|---|
| `django` | Built from `Dockerfile` | 8000 | Web application + API |
| `celery` | Built from `Dockerfile` | — | Async task worker |
| `celery_beat` | Built from `Dockerfile` | — | Periodic task scheduler |
| `postgres` | `postgres:16-alpine` | 5432 | Primary database |
| `redis` | `redis:7.2-alpine` | 6379 | Celery broker + cache |
| `prometheus` | `prom/prometheus:v2.50.0` | 9090 | Metrics storage |
| `alertmanager` | `prom/alertmanager:v0.27.0` | 9093 | Alert routing |
| `grafana` | `grafana/grafana:10.4.0` | 3000 | Visualization |
| `snmp_exporter` | `prom/snmp-exporter:v0.25.0` | 9116 | SNMP → Prometheus bridge |
| `node_exporter` | `prom/node-exporter:v1.7.0` | 9100 | Host metrics |

### Networks

| Network | Services | Purpose |
|---|---|---|
| `backend` | django, celery, celery_beat, postgres, redis | Application + database communication |
| `monitoring` | django, prometheus, alertmanager, grafana, snmp_exporter, node_exporter | Metrics and alerting |
| `eve_ng` | django, snmp_exporter | Communication with EVE-NG devices |

### Health checks

PostgreSQL and Redis have health checks. Django `depends_on` waits for them to be healthy before starting:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

The entrypoint's `pg_isready` loop provides a second layer of safety.

### Volumes (persistent data)

| Volume | Service | What it stores |
|---|---|---|
| `postgres_data` | postgres | All database tables |
| `redis_data` | redis | Celery task results |
| `prometheus_data` | prometheus | 30 days of metrics (TSDB) |
| `grafana_data` | grafana | Users, alert rules, UI-created dashboards |
| `static_files` | django | Collected static assets (shared with nginx if added) |

---

## Useful Docker Commands

```bash
# Start all services
docker compose up -d

# View logs for Django
docker compose logs -f django

# View logs for all services
docker compose logs -f

# Run a management command
docker compose exec django python manage.py shell

# Run a one-off migration
docker compose exec django python manage.py migrate

# Open a bash shell inside the Django container
docker compose exec django bash

# Rebuild the Django image after code changes
docker compose build django && docker compose up -d django

# Check all service health
docker compose ps

# Stop and remove all containers (keeps volumes)
docker compose down

# Stop and remove everything including volumes (WARNING: deletes database)
docker compose down -v
```
