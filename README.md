# DevSecOps Platform — Network Infrastructure Automation

A production-ready **DevSecOps platform** for centralized management, monitoring, provisioning, and security compliance enforcement on Cisco network devices inside an EVE-NG emulated enterprise network.

Inspired by **Cisco DNA Center (DNAC)** — built entirely with open-source tools.

---

## Table of Contents

1. [Concept & Goals](#1-concept--goals)
2. [Network Topology](#2-network-topology)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Docker Services](#5-docker-services)
6. [Django Applications](#6-django-applications)
7. [Data Flow](#8-data-flow)
8. [API Reference](#9-api-reference)
9. [Security Design](#10-security-design)
10. [CI/CD Pipeline](#11-cicd-pipeline)
11. [Quick Start](#12-quick-start)

---

## 1. Concept & Goals

Modern enterprise networks require more than manual CLI work. This platform provides a **single pane of glass** for network operations teams to:

| Capability | Description |
|---|---|
| **Inventory** | Central database of all network devices with real-time status |
| **Discovery** | SNMP-based polling to detect devices and collect metrics |
| **Provisioning** | Push Jinja2 config templates to devices via SSH — with before/after diff |
| **Monitoring** | Prometheus + Grafana dashboards embedded in the UI; AlertManager webhook receiver |
| **Compliance** | 12 regex-based security rules evaluated against live running-configs |
| **Drift Detection** | Compare golden baseline configs against actual device configs |
| **RBAC** | Three roles (Admin, Engineer, Read-Only) enforced on both UI and REST API |
| **Audit Trail** | Every config push is logged with the rendered config, diff, status, and executor |

The platform sits on the **management network** (`192.168.100.0/24`) and reaches every device via SSH and SNMP. Prometheus scrapes the same network via the SNMP Exporter.

---

## 2. Network Topology

Three-site enterprise network emulated in **EVE-NG**:

```
                          ┌─────────────────┐
                          │   WAN Switch    │
                          │  192.168.100.5  │
                          └────────┬────────┘
               ┌───────────────────┼──────────────────┐
               │                   │                  │
    ┌──────────┴──────┐  ┌─────────┴──────┐  ┌───────┴────────┐
    │   SOFIA (HQ)    │  │    BURGAS       │  │    PLOVDIV     │
    │─────────────────│  │────────────────│  │────────────────│
    │ FW Primary      │  │ Router          │  │ Router         │
    │ 192.168.100.11  │  │ 192.168.100.21  │  │ 192.168.100.31 │
    │ FW Secondary    │  │ FW Primary      │  │ FW Primary     │
    │ 192.168.100.12  │  │ 192.168.100.22  │  │ 192.168.100.32 │
    │ Router          │  │ L2 Switch       │  │ L2 Switch      │
    │ 192.168.100.13  │  │ 192.168.100.23  │  │ 192.168.100.33 │
    │ L2 Switch       │  └────────────────┘  └────────────────┘
    │ 192.168.100.14  │
    └─────────────────┘

    Management network: 192.168.100.0/24
    All devices reachable via SSH (port 22) and SNMP (UDP 161)
```

**9 devices total** across 4 categories:
- `router` — Cisco IOS routers (OSPF, BGP)
- `firewall_primary` / `firewall_secondary` — Cisco ASA pairs
- `l2_switch` — Cisco IOS Layer-2 switches
- `wan_switch` — WAN aggregation switch

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                          │
│                                                                      │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  Browser │───▶│    Django    │───▶│         SQLite           │  │
│  │          │    │  (Gunicorn)  │    │       (WAL mode)         │  │
│  └──────────┘    │   port 8000  │    └──────────────────────────┘  │
│                  └──────┬───────┘                                    │
│                         │                                            │
│              ┌──────────┼──────────┐                                │
│              ▼          ▼          ▼                                │
│          ┌───────┐  ┌───────┐  ┌──────────────────────────────┐   │
│          │ Redis │  │Celery │  │      External Services        │   │
│          │:6379  │  │Workers│  │  ┌──────────┐ ┌──────────┐   │   │
│          └───────┘  └───┬───┘  │  │Prometheus│ │ Grafana  │   │   │
│                         │      │  │  :9090   │ │  :3000   │   │   │
│                         │      │  └────┬─────┘ └──────────┘   │   │
│                         │      │       │       ┌──────────┐    │   │
│                         │      │  ┌────┴─────┐ │AlertMgr  │   │   │
│                         │      │  │SNMP Expt │ │  :9093   │   │   │
│                         │      │  │  :9116   │ └──────────┘   │   │
│                         │      │  └──────────┘                │   │
│                         │      └──────────────────────────────┘   │
│                         │                                           │
│              ┌──────────┼──────────────────────┐                   │
│              ▼          ▼                       ▼                   │
│     ┌─────────────────────────────────────────────────┐            │
│     │            EVE-NG Management Network             │            │
│     │                 192.168.100.0/24                 │            │
│     │  [Router] [Switch] [FW-Primary] [FW-Secondary]  │            │
│     └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

**Request flow for a config push:**
1. Engineer submits a push request via the UI
2. Django validates the request and enqueues a Celery task
3. Celery worker SSHes to the device via Netmiko
4. Worker captures `show running-config` before and after
5. Unified diff is computed and stored in the `AuditLog`
6. Task result (success/failed) is polled by the browser every 2.5 seconds

---

## 4. Technology Stack

### Backend
| Component | Technology | Version |
|---|---|---|
| Web framework | Django | 4.2 |
| REST API | Django REST Framework | 3.15 |
| Authentication | JWT (SimpleJWT) | 5.3 |
| Task queue | Celery | 5.3 |
| Message broker | Redis | 7 |
| Database | SQLite (WAL mode) | Built-in |
| SSH automation | Netmiko | 4.3 |
| SNMP | puresnmp | 2.0 |
| Config templating | Jinja2 | 3.1 |
| Password encryption | Fernet (cryptography) | 42.x |
| API docs | drf-spectacular (OpenAPI 3) | 0.27 |
| Static files | WhiteNoise | 6.6 |

### Frontend
| Component | Technology |
|---|---|
| UI framework | Bootstrap 5 (dark theme) |
| Icons | Bootstrap Icons |
| Fonts | Inter (UI), JetBrains Mono (code) |
| Topology map | Custom SVG + JavaScript |
| Charts | Embedded Grafana iframes |

### Observability
| Component | Technology | Port |
|---|---|---|
| Metrics collection | Prometheus | 9090 |
| Device SNMP metrics | SNMP Exporter | 9116 |
| Host metrics | Node Exporter | 9100 |
| Dashboards | Grafana 10 | 3000 |
| Alert routing | AlertManager | 9093 |

### DevSecOps
| Stage | Tool |
|---|---|
| Style lint | flake8 |
| SAST | Bandit |
| Dependency CVEs | pip-audit |
| Unit tests | Django TestCase + coverage |
| Container scan | Trivy |
| CI/CD | GitHub Actions |

---

## 5. Docker Services

The entire stack runs as **9 containers** defined in `docker-compose.yml`:

```
┌─────────────────┬────────────┬──────────────────────────────────────┐
│ Service         │ Port(s)    │ Role                                 │
├─────────────────┼────────────┼──────────────────────────────────────┤
│ django          │ 8000       │ Web UI + REST API (gunicorn, 4 workers│
│ celery          │ —          │ Async task workers (4 queues)         │
│ celery-beat     │ —          │ Periodic task scheduler              │
│ redis           │ 6379       │ Celery broker + Django cache         │
│ prometheus      │ 9090       │ Metrics scraper (30d retention)      │
│ snmp_exporter   │ 9116       │ Translates SNMP to Prometheus format │
│ node_exporter   │ 9100       │ Host OS metrics                      │
│ grafana         │ 3000       │ Dashboard UI (anonymous viewer mode) │
│ alertmanager    │ 9093       │ Routes alerts → Django webhook        │
└─────────────────┴────────────┴──────────────────────────────────────┘
```

### Celery Task Queues

Celery workers listen on **4 named queues**, each with a specific purpose:

| Queue | Used by | Tasks |
|---|---|---|
| `discovery` | Inventory app | SNMP polls, device status updates |
| `provisioning` | Provisioning app | SSH config pushes |
| `monitoring` | Monitoring app | Alert sync, device down handler |
| `default` | Security app | Compliance checks, drift detection |

### Periodic Tasks (Celery Beat)

| Task | Schedule | Purpose |
|---|---|---|
| `poll-all-devices` | Every 5 min | SNMP poll all devices, update status |
| `sync-prometheus-alerts` | Every 2 min | Reconcile alerts from Prometheus API |
| `mark-devices-from-alerts` | Every 3 min | Sync device status from active alerts |
| `daily-compliance-check` | 02:00 EET | Run all compliance rules on all UP devices |
| `daily-drift-check` | 03:00 EET | Golden config drift on all UP devices |

---

## 6. Django Applications

The project is split into **5 Django apps** under `apps/`:

---

### `apps/accounts` — Authentication & User Management

Handles everything related to users and access control.

**Models:**
- `User` — Extends Django's `AbstractUser` with a `role` field

**Roles and permissions:**

| Role | Can do |
|---|---|
| `admin` | Full access — user management, all CRUD, can push configs |
| `engineer` | Can read/write devices, push configs, run checks — cannot manage users |
| `readonly` | Read-only access to all data — no writes, no pushes |

**Key files:**
- `models.py` — `User` model with `is_admin()` / `is_engineer()` methods
- `decorators.py` — `@admin_required`, `@engineer_required` for view-level RBAC
- `permissions.py` — `IsAdminUser`, `IsEngineerOrReadOnly` for DRF API-level RBAC
- `serializers.py` — `CustomTokenObtainPairSerializer` (JWT claims include `role`, `is_admin`, `is_engineer`)
- `api.py` — `UserViewSet` with `/me/`, `/set-role/`, `/toggle-active/` actions

**Views:**
- `/accounts/login/` — Login page with rate limiting (10 POST/min per IP)
- `/accounts/profile/` — Edit first/last name, email; view audit action count
- `/accounts/password-change/` — Change password (keeps session alive)
- `/accounts/users/` — Admin-only user management table with live role change

---

### `apps/inventory` — Device Inventory & Discovery

The source of truth for all network devices.

**Model: `Device`**

| Field | Purpose |
|---|---|
| `hostname` | Unique device identifier (e.g. `R-SOFIA-01`) |
| `ip_address` | Management IP in `192.168.100.0/24` |
| `site` | `sofia` / `burgas` / `plovdiv` / `wan` |
| `device_type` | `router` / `firewall_primary` / `firewall_secondary` / `l2_switch` / `wan_switch` |
| `status` | `up` / `down` / `unknown` — updated by Celery tasks |
| `ssh_username` | SSH login username |
| `ssh_password` | **Fernet-encrypted** SSH password at rest |
| `snmp_community` | SNMP community string for polling |
| `last_seen` | Timestamp of last successful SNMP response |

**SSH credential security:**
Passwords are encrypted with Fernet (symmetric AES-128-CBC) before storage. The `FIELD_ENCRYPTION_KEY` environment variable holds the key. Plaintext is only ever decrypted inside Celery workers at task execution time — never stored in plaintext, never logged.

**Celery tasks:**
- `poll_device(device_id)` — SNMP GET to check reachability, calls `device.mark_seen()` or `device.mark_down()`
- `poll_all_devices()` — Dispatches `poll_device` for every device in the inventory

**Views:**
- `/` — Dashboard with stat cards (devices up/down, active alerts, sites) + animated SVG topology map
- `/inventory/` — Device list with site/type/status filters
- `/inventory/<id>/` — Device detail: info, provisioning history, compliance results

---

### `apps/provisioning` — Template-Based Config Push

Enables engineers to push standardized configurations to devices via SSH.

**Models:**

`ProvisioningTemplate` — Config template stored in the database:
| Field | Purpose |
|---|---|
| `name` | Unique template name (e.g. `ntp-config`) |
| `content` | Jinja2 template body — can use `{{ device.hostname }}`, `{{ ntp_primary }}`, etc. |
| `device_type` | Optional filter — restricts which device types can use this template |
| `site` | Optional filter — restricts which site this template applies to |

`AuditLog` — Immutable record of every push:
| Field | Purpose |
|---|---|
| `device` | Which device was targeted |
| `template_name` | Which template was used |
| `config_sent` | Full rendered config that was pushed |
| `config_diff` | Unified diff of running-config before vs after |
| `status` | `pending` / `success` / `failed` |
| `execution_time` | Task duration in seconds |
| `user` | Who triggered the push |

**How a config push works:**
1. Engineer selects template + target device(s) in the UI
2. (Optional) Preview renders the Jinja2 template with device context — no SSH needed
3. Push is submitted → Celery task is queued on the `provisioning` queue
4. Task opens SSH via Netmiko → captures `show running-config` (before)
5. Sends rendered config lines via `send_config_set()`
6. Saves config → captures `show running-config` (after)
7. Computes `difflib.unified_diff(before, after)` → stores in `AuditLog`
8. Browser polls task status every 2.5 seconds until complete

**Views:**
- `/provisioning/` — Template list + push interface (two-panel AJAX layout)
- `/provisioning/push/` — Select template + devices, real-time push log
- `/provisioning/audit/` — Full audit log with filters
- `/provisioning/audit/<id>/` — Syntax-colored unified diff viewer

---

### `apps/monitoring` — Alerts & Dashboards

Integrates with Prometheus + AlertManager to bring network alerts into the platform.

**Model: `Alert`**

| Field | Purpose |
|---|---|
| `fingerprint` | AlertManager fingerprint — unique per alert, prevents duplicates |
| `alertname` | e.g. `DeviceDown`, `InterfaceDown`, `HighCPULoad` |
| `instance` | Source device IP or hostname |
| `site` | Which site the alert belongs to |
| `severity` | `critical` / `warning` / `info` |
| `status` | `firing` / `resolved` |
| `acknowledged` | Whether an engineer has acknowledged the alert |
| `ack_note` | Free-text acknowledgement note |
| `raw_payload` | Full JSON payload from AlertManager (stored for debugging) |

**AlertManager webhook flow:**
1. Prometheus detects a problem (e.g. device unreachable) → fires alert rule
2. AlertManager receives alert, groups and routes it
3. AlertManager POSTs to `POST /api/alerts/webhook/` (no auth required)
4. Django uses `update_or_create(fingerprint=...)` — identical alerts deduplicate
5. For `DeviceDown` alerts: immediately marks the device status as `down` in inventory
6. Dispatches `mark_devices_from_alerts` Celery task as reconciliation fallback

**Deduplication strategy:** AlertManager can fire the same alert multiple times (repeat_interval). The `fingerprint` field ensures Django always updates the existing record instead of creating duplicates.

**Inhibition rules:** When a `DeviceDown` alert fires, AlertManager suppresses downstream `InterfaceDown` and `HighInterfaceErrors` alerts for the same device — preventing alert storms.

**Views:**
- `/monitoring/` — Active alert list with filters (severity, status, site, acknowledged)
- `/monitoring/alerts/` — Alert table with inline AJAX acknowledge
- `/monitoring/dashboards/` — Grafana dashboards embedded as iframes

---

### `apps/security` — Compliance & Drift Detection

Automated security auditing against Cisco IOS configurations.

**Models:**

`ComplianceRule` — A single security check:
| Field | Purpose |
|---|---|
| `pattern` | Python regex searched against the full running-config |
| `match_means_pass` | `True` = pattern found → PASS; `False` = pattern found → FAIL (absence check) |
| `severity` | `critical` / `warning` / `info` |
| `category` | Grouping label (e.g. `SSH`, `AAA`, `NTP`, `SNMP`) |
| `device_types` | JSON list of applicable device types; empty = all devices |
| `remediation` | CLI commands that fix this finding |

**12 built-in compliance rules** (loaded from `fixtures/compliance_rules.json`):

| Rule | Severity | Type |
|---|---|---|
| SSH v2 enabled | Critical | Presence |
| Telnet disabled | Critical | Absence |
| AAA new-model | Critical | Presence |
| No enable password | Critical | Absence |
| NTP server configured | Warning | Presence |
| SNMP community with ACL | Warning | Presence |
| Syslog host configured | Warning | Presence |
| Service password-encryption | Warning | Presence |
| OSPF MD5 authentication | Warning | Presence (routers/firewalls only) |
| CDP disabled on firewalls | Warning | Absence (firewalls only) |
| Login banner present | Info | Presence |
| Service timestamps log | Info | Presence |

`ComplianceResult` — Result of evaluating one rule on one device:
- `status`: `pass` / `fail` / `error` / `skipped`
- `evidence`: The matched config line (for passing checks)
- `checked_at`: When the check ran

**Compliance scoring:**
- Per-device score = `(pass_count / total_applicable_rules) × 100`
- A device is **compliant** if score ≥ 80%
- Latest result per (device, rule) pair is used — historical runs don't inflate the score

`GoldenConfig` — Expected baseline configuration per device type:
- Stored as plain-text expected config lines
- One golden config per device type (router, switch, etc.)
- Versioned (`version` field increments on update)

`DriftResult` — Output of a drift detection run:
- `diff`: Unified diff (`golden → actual`)
- `drift_lines`: Count of `+`/`-` lines in the diff
- `status`: `clean` / `drifted` / `error`

**How drift detection works:**
1. Fetch `show running-config` via SSH
2. Strip blank lines and trailing whitespace from both golden and actual configs
3. Run `difflib.unified_diff(golden_lines, actual_lines)`
4. Count `+` and `-` lines → `drift_lines`
5. Store diff as text — displayed with syntax colouring (green=added, red=removed, blue=header)

**Views:**
- `/security/` — Summary with compliance scores and drift status cards
- `/security/compliance/` — Per-device compliance scores with progress bars
- `/security/compliance/<id>/` — Rule-by-rule breakdown with evidence and remediation
- `/security/drift/` — Drift status table for all devices with golden configs
- `/security/drift/<id>/` — Full unified diff viewer with scan history

---

## 7. Data Flow

### SNMP Monitoring Loop
```
Celery Beat (every 5 min)
  └── poll_all_devices()
        └── poll_device(id) [per device, discovery queue]
              └── puresnmp.get(device.ip, 'sysDescr', community)
                    ├── success → device.mark_seen() → status=up
                    └── failure → device.mark_down() → status=down
```

### Prometheus Alert Pipeline
```
Device unreachable
  └── Prometheus fires alert rule (alerts.yml)
        └── AlertManager routes alert
              └── POST /api/alerts/webhook/ (AllowAny)
                    ├── Alert.objects.update_or_create(fingerprint=...)
                    ├── DeviceDown? → Device.objects.filter(ip=instance).update(status='down')
                    └── mark_devices_from_alerts.apply_async(countdown=5)
```

### Config Push Pipeline
```
Engineer clicks "Push"
  └── POST /api/provisioning/push/
        └── push_config_to_device.apply_async() [provisioning queue]
              ├── AuditLog(status=pending)
              ├── ConnectHandler(host, user, password_plaintext)
              ├── before = send_command('show running-config')
              ├── send_config_set(rendered_lines)
              ├── save_config()
              ├── after = send_command('show running-config')
              ├── diff = unified_diff(before, after)
              └── AuditLog(status=success, config_diff=diff)
```

---

## 8. API Reference

Base URL: `http://localhost:8000/api/`

Interactive docs: `http://localhost:8000/api/docs/` (Swagger UI)

### Authentication
```
POST /api/token/          → { access, refresh }   (JWT, role embedded in claims)
POST /api/token/refresh/  → { access }
POST /api/token/verify/   → 200 if valid
```

### Accounts
```
GET  /api/accounts/users/                    → List all users (admin only)
GET  /api/accounts/users/me/                 → Current user info (any auth)
POST /api/accounts/users/{id}/set-role/      → Change user role (admin only)
POST /api/accounts/users/{id}/toggle-active/ → Activate/deactivate user (admin only)
```

### Inventory
```
GET    /api/devices/              → List devices (filterable: site, status, device_type)
POST   /api/devices/              → Create device (engineer+)
GET    /api/devices/{id}/         → Device detail
PATCH  /api/devices/{id}/         → Update device (engineer+)
DELETE /api/devices/{id}/         → Delete device (admin only)
GET    /api/dashboard/stats/      → { total, up, down, unknown, active_alerts }
```

### Provisioning
```
GET    /api/provisioning/templates/        → List templates
POST   /api/provisioning/templates/        → Create template (engineer+)
POST   /api/provisioning/render/           → Preview rendered template (no SSH)
POST   /api/provisioning/push/             → Push config to device(s)
GET    /api/provisioning/task/{task_id}/   → Poll async task status
GET    /api/provisioning/audit/            → Audit log (filterable)
```

### Monitoring
```
POST /api/alerts/webhook/                      → AlertManager receiver (no auth)
GET  /api/monitoring/alerts/                   → List alerts (filterable)
POST /api/monitoring/alerts/{id}/acknowledge/  → Acknowledge alert
GET  /api/monitoring/alerts/active-summary/    → Count by severity
```

### Security
```
GET  /api/security/rules/                          → Compliance rules
GET  /api/security/results/                        → Compliance results
GET  /api/security/compliance/summary/             → Per-device scores
POST /api/security/compliance/run/{device_id}/     → Run checks on one device
POST /api/security/compliance/run-all/             → Run checks on all UP devices
POST /api/security/drift/run/{device_id}/          → Drift check on one device
POST /api/security/drift/run-all/                  → Drift check on all UP devices
GET  /api/security/golden/                         → Golden config baselines
GET  /api/security/drift/                          → Drift results
```

---

## 9. Security Design

### Authentication & Authorisation
- **Session auth** for the web UI (Django sessions with 8-hour TTL)
- **JWT auth** for the REST API (access token lifetime: 8 hours, refresh: 7 days)
- JWT payload includes `role`, `is_admin`, `is_engineer` claims — clients don't need a separate API call to determine capabilities
- Token blacklisting on refresh rotation via `rest_framework_simplejwt.token_blacklist`

### Credential Protection
- SSH passwords are **Fernet-encrypted** at rest (`cryptography` library, AES-128-CBC + HMAC)
- Encryption key stored in `FIELD_ENCRYPTION_KEY` env var — never in code or DB
- Passwords are decrypted only inside Celery workers, only at SSH connection time
- The REST API serializer marks `ssh_password` as `write_only` — never returned in API responses

### Rate Limiting
- Login endpoint: **10 POST requests per minute per IP** (`django-ratelimit`)
- Backed by Redis in production; returns `403` with a human-readable message when exceeded

### HTTP Security Headers (production)
| Header | Value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` |
| `Content-Security-Policy` | `default-src 'self'; frame-src 'self' <grafana-url>; object-src 'none'` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-Content-Type-Options` | `nosniff` |

### AlertManager Webhook
- Intentionally **public** (`AllowAny`) — AlertManager calls it without credentials
- Protected by network isolation: only the `netops` Docker network can reach Django port 8000
- Deduplication via `fingerprint` prevents replay/flood attacks from creating duplicate records

---

## 10. CI/CD Pipeline

**GitHub Actions** workflow (`.github/workflows/devsecops.yml`) — 5 parallel jobs:

```
push to main / PR
  ├── lint         → flake8 (max 120 chars, excludes migrations)
  ├── bandit       → Python SAST — fails on HIGH severity
  ├── pip-audit    → Dependency CVE scan — fails on any known vuln
  ├── test         → Django unit tests (70 test cases) + coverage ≥ 50%
  └── trivy        → Container scan (needs: test) — fails on CRITICAL CVEs
```

All scan reports are uploaded as workflow artifacts (14-day retention).

**Test coverage areas:**
- User model: role flags, badge colors, permission methods
- Login/logout: correct credentials, wrong password, rate limiting disabled in tests
- Profile: auth gate, update persistence
- Device API: list, create, filter — permission matrix per role
- Alert webhook: creates alert, idempotent on repeat, resolves on `status=resolved`
- Compliance rules: presence checks, absence checks, case-insensitivity, evidence extraction
- Provisioning: template CRUD permission matrix

---

## 11. Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd DevSecOpsPlatform

# 2. Configure environment
cp .env.example .env
# Generate SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Generate FIELD_ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste both into .env

# 3. Add static route to EVE-NG devices (Linux/WSL2)
sudo ip route add 192.168.100.0/24 via <eve-ng-mgmt-ip>

# 4. Start the stack
docker compose up -d --build

# 5. Create admin user
docker compose exec django python manage.py createsuperuser

# 6. Open http://localhost:8000
```

See [SETUP.md](SETUP.md) for the complete setup guide including production deployment, troubleshooting, and common operations.

---

## Project Structure

```
DevSecOpsPlatform/
├── apps/
│   ├── accounts/       # Auth, RBAC, user management
│   ├── inventory/      # Device inventory, SNMP discovery
│   ├── provisioning/   # Config templates, SSH push, audit log
│   ├── monitoring/     # Alerts, AlertManager webhook, Grafana
│   └── security/       # Compliance rules, golden config drift
├── api/
│   └── urls.py         # Central DRF router — all /api/* endpoints
├── config/
│   ├── settings/
│   │   ├── base.py     # Shared settings
│   │   ├── dev.py      # Development overrides
│   │   ├── prod.py     # Production hardening (HTTPS, CSP, HSTS)
│   │   └── test.py     # CI test settings (in-memory SQLite, no Redis)
│   ├── celery.py       # Celery app + autodiscovery
│   └── db_pragmas.py   # SQLite WAL mode via connection_created signal
├── templates/          # Django HTML templates (Bootstrap 5 dark theme)
├── static/
│   └── js/topology.js  # Animated SVG network topology map
├── fixtures/
│   ├── devices.json          # 9 EVE-NG devices
│   └── compliance_rules.json # 12 security rules
├── prometheus/
│   ├── prometheus.yml        # Scrape config (9 SNMP targets)
│   ├── alertmanager.yml      # Routing + inhibition rules
│   └── rules/alerts.yml      # Alert rule definitions
├── grafana/
│   ├── dashboards/           # Provisioned network overview dashboard
│   └── datasources/          # Prometheus datasource config
├── snmp_exporter/
│   └── snmp.yml              # SNMP OID mappings for Cisco IOS
├── .github/workflows/
│   └── devsecops.yml         # CI/CD pipeline (lint, SAST, audit, test, Trivy)
├── Dockerfile                # python:3.11-slim, non-root appuser
├── docker-compose.yml        # 9-service stack definition
├── entrypoint.sh             # migrate + collectstatic + loaddata on startup
├── requirements.txt          # All Python dependencies pinned
├── pyproject.toml            # Bandit + coverage config
├── .flake8                   # Flake8 config
├── .env.example              # Environment variable template
├── SETUP.md                  # Full setup and operations guide
└── README.md                 # This file
```
