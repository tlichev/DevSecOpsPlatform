# DevSecOps Platform — Setup Guide

End-to-end initialization guide for the 3-site EVE-NG network automation platform.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Docker Engine | 24.x | `docker --version` |
| Docker Compose | v2 (plugin) | `docker compose version` |
| Python | 3.11 | Only needed for key generation outside Docker |
| EVE-NG | Community or Pro | Topology must be running before starting the stack |
| Host OS | Linux / WSL2 | Windows hosts need WSL2 for the `mgmt` bridge network |

---

## 1. Clone the Repository

```bash
git clone <your-repo-url> DevSecOpsPlatform
cd DevSecOpsPlatform
```

---

## 2. Generate Secret Keys

Run these commands **once** and paste the output into `.env`.

```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Fernet key for encrypting device SSH passwords at rest
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If Python is not available locally, run inside a temporary container:

```bash
docker run --rm python:3.11-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 3. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in **at minimum**:

```dotenv
SECRET_KEY=<output from step 2>
FIELD_ENCRYPTION_KEY=<output from step 2>
GRAFANA_ADMIN_PASSWORD=<strong-password>
ALLOWED_HOSTS=localhost,127.0.0.1
LOAD_FIXTURES=1
```

Set `LOAD_FIXTURES=0` after the first boot to avoid re-importing demo data.

---

## 4. Add Static Route to EVE-NG Management Network

The Celery workers need to reach device management IPs (`192.168.100.0/24`)
directly. Add a host route before starting the stack.

**Linux / WSL2:**
```bash
# Replace 192.168.56.101 with the IP of your EVE-NG management interface
sudo ip route add 192.168.100.0/24 via 192.168.56.101
```

**To make it persistent (systemd-networkd or /etc/rc.local):**
```bash
# /etc/rc.local
ip route add 192.168.100.0/24 via 192.168.56.101
```

Verify reachability before continuing:
```bash
ping -c 2 192.168.100.1
```

---

## 5. Build and Start the Stack

```bash
# Build the Django image and start all 9 services
docker compose up -d --build

# Tail logs from all services (Ctrl-C to stop following)
docker compose logs -f
```

The `django` container automatically runs on startup (via `entrypoint.sh`):
1. Waits for Redis to be healthy
2. `python manage.py migrate` — creates/updates the SQLite schema
3. `python manage.py collectstatic` — copies static files to `/app/staticfiles`
4. Loads `fixtures/devices.json` and `fixtures/compliance_rules.json` (if `LOAD_FIXTURES=1`)
5. Starts gunicorn on port 8000

Wait for the health check to pass before continuing:
```bash
docker compose ps          # all services should show "healthy" or "running"
curl http://localhost:8000/health/   # → {"status": "ok"}
```

---

## 6. Create the Superuser

```bash
docker compose exec django python manage.py createsuperuser
```

Enter a username, email, and strong password. This account gets full admin access.

---

## 7. Load Fixtures (if LOAD_FIXTURES was 0)

```bash
# 9 EVE-NG devices across 3 sites
docker compose exec django python manage.py loaddata fixtures/devices.json

# 12 security compliance rules (SSH, AAA, NTP, SNMP ACL, …)
docker compose exec django python manage.py loaddata fixtures/compliance_rules.json
```

---

## 8. Verify the Full Stack

| Service | URL | Default credentials |
|---|---|---|
| Django Platform | http://localhost:8000 | Superuser from step 6 |
| Django Admin | http://localhost:8000/admin/ | Superuser from step 6 |
| API Docs (Swagger) | http://localhost:8000/api/docs/ | — |
| Grafana | http://localhost:3000 | admin / `GRAFANA_ADMIN_PASSWORD` |
| Prometheus | http://localhost:9090 | — |
| AlertManager | http://localhost:9093 | — |

Quick smoke test:
```bash
# Platform login page
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/accounts/login/
# → 200

# JWT token (replace credentials)
curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}' | python -m json.tool

# Device list (with Bearer token from above)
curl -s http://localhost:8000/api/devices/ \
  -H "Authorization: Bearer <access_token>" | python -m json.tool
```

---

## 9. After Initial Setup

**Disable fixture loading** to avoid re-importing on container restarts:
```bash
# In .env:
LOAD_FIXTURES=0
docker compose up -d   # re-create containers to pick up .env change
```

**Create additional users** (Django Admin → Accounts → Users, or API):
```bash
# Via management command:
docker compose exec django python manage.py createsuperuser

# Or create an engineer / readonly account in Django Admin:
# http://localhost:8000/admin/accounts/user/add/
```

---

## 10. Run CI Checks Locally

Before pushing, run the same checks the GitHub Actions pipeline runs:

```bash
# Install dev tools
pip install flake8 bandit pip-audit coverage

# Lint
flake8 apps/ api/ config/ --max-line-length=120 --extend-ignore=E203,W503 --exclude=migrations

# SAST
bandit -r apps/ api/ config/ --skip B101,B105,B106,B311,B603,B607 -f screen

# Dependency audit
pip-audit -r requirements.txt

# Django tests with coverage
coverage run manage.py test apps/ --settings=config.settings.test --verbosity=2
coverage report --fail-under=50
```

---

## 11. Common Operations

### Restart a single service
```bash
docker compose restart celery
docker compose restart django
```

### Rebuild after code changes
```bash
docker compose up -d --build django celery celery-beat
```

### Open a Django shell
```bash
docker compose exec django python manage.py shell
```

### Run compliance checks manually
```bash
# Via API (replace <token> with a valid JWT)
curl -X POST http://localhost:8000/api/security/compliance/run-all/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'

# Or from the Security → Compliance page in the UI
```

### Run drift detection manually
```bash
curl -X POST http://localhost:8000/api/security/drift/run-all/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Reload Prometheus config (without restart)
```bash
curl -X POST http://localhost:9090/-/reload
```

### View Celery task results
```bash
# Recent tasks in the DB
docker compose exec django python manage.py shell -c "
from django_celery_results.models import TaskResult
for t in TaskResult.objects.order_by('-date_done')[:10]:
    print(t.task_id[:16], t.status, t.task_name)
"
```

---

## 12. Production Deployment Checklist

Switch `DJANGO_SETTINGS_MODULE` to `config.settings.prod` before going live.

```bash
# In .env:
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<strong-50-char-random-key>
ALLOWED_HOSTS=netops.yourdomain.com
```

Then verify Django's deployment check passes:
```bash
docker compose exec django python manage.py check --deploy
```

Additional steps for production:
- [ ] Place an nginx reverse proxy in front of gunicorn for TLS termination
- [ ] Set `SECURE_HSTS_PRELOAD=True` only after testing HTTPS end-to-end
- [ ] Rotate `FIELD_ENCRYPTION_KEY` using a re-encryption migration if devices already exist
- [ ] Change default Grafana admin password (`GRAFANA_ADMIN_PASSWORD`)
- [ ] Restrict AlertManager webhook to the Docker internal network only
- [ ] Set up log aggregation (forward Docker logs to ELK or similar)
- [ ] Back up `db.sqlite3` on a schedule (cron + `VACUUM` before copy)

---

## 13. Troubleshooting

**Celery tasks not running:**
```bash
docker compose logs celery | tail -30
# Ensure Redis is healthy:
docker compose exec redis redis-cli ping   # → PONG
```

**Migrations failing:**
```bash
docker compose exec django python manage.py showmigrations
docker compose exec django python manage.py migrate --verbosity=2
```

**Device SSH timeouts (Netmiko):**
- Verify the static route is in place: `ip route show 192.168.100.0/24`
- Ping the device: `docker compose exec celery ping -c 2 192.168.100.10`
- Check SSH is enabled on the device: `show ip ssh` (from EVE-NG console)

**Grafana dashboard not loading in iframe:**
- Confirm `GRAFANA_BROWSER_URL` in `.env` matches the URL your browser uses
- Grafana requires `GF_SECURITY_ALLOW_EMBEDDING=true` (already set in `docker-compose.yml`)

**Prometheus not scraping devices:**
- Check targets: http://localhost:9090/targets
- Verify SNMP community string matches `SNMP_DEFAULT_COMMUNITY` in `.env`
- Ensure the `mgmt` Docker network can reach `192.168.100.0/24`
