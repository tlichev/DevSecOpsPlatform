# DevSecOps Platform for Network Enterprise Infrastructure Automation

A production-ready, Django-based network management platform inspired by Cisco DNAC. It centrally manages, monitors, provisions, and enforces security compliance on network devices running inside an EVE-NG emulated enterprise network.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Services and Ports](#services-and-ports)
- [Application Modules](#application-modules)
- [Network Topology](#network-topology)
- [Data Flow](#data-flow)
- [Authentication and RBAC](#authentication-and-rbac)
- [Environment Variables](#environment-variables)
- [CI/CD Pipeline](#cicd-pipeline)
- [Development Workflow](#development-workflow)
- [Component READMEs](#component-readmes)

---

## Overview

This platform provides a single pane of glass for:

| Capability | Description |
|---|---|
| **Inventory** | Full CRUD for network devices with automatic subnet discovery via ICMP + SNMP |
| **Provisioning** | Push Jinja2-rendered configurations to devices over SSH via Netmiko, asynchronously via Celery |
| **Monitoring** | Prometheus + SNMP Exporter collect metrics; Grafana dashboards embedded in the UI; AlertManager routes alerts back to Django |
| **Security & Compliance** | SSH v2, Telnet-disabled, ACL, SNMP v3 checks; config snapshot and drift detection; full audit log |
| **REST API** | Complete DRF API with JWT authentication and rate limiting |
| **CI/CD** | GitHub Actions: lint → SAST (Bandit) → pip-audit → Trivy → test → build → deploy |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Host                          │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐                     │
│  │  Django  │   │  Celery  │   │ Celery Beat │                     │
│  │  :8000   │   │  Worker  │   │ (scheduler) │                     │
│  └────┬─────┘   └────┬─────┘   └──────┬──────┘                     │
│       │              │                │                             │
│  ┌────▼──────────────▼────────────────▼──────┐                     │
│  │              Redis (broker :6379)          │                     │
│  └────────────────────────────────────────────┘                     │
│                                                                     │
│  ┌─────────────┐   ┌──────────────┐                                 │
│  │  PostgreSQL │   │   Grafana    │                                 │
│  │    :5432    │   │    :3000     │                                 │
│  └─────────────┘   └──────┬───────┘                                 │
│                            │                                        │
│  ┌─────────────────────────▼──────────────────┐                     │
│  │            Prometheus :9090                 │                     │
│  └────┬──────────────┬──────────────┬──────────┘                     │
│       │              │              │                               │
│  ┌────▼────┐  ┌──────▼──────┐  ┌───▼──────────┐                    │
│  │  SNMP   │  │    Node     │  │ AlertManager │                    │
│  │Exporter │  │  Exporter   │  │    :9093     │                    │
│  │ :9116   │  │   :9100     │  └──────┬───────┘                    │
│  └────┬────┘  └─────────────┘         │                            │
│       │                               │ webhook POST               │
└───────┼───────────────────────────────┼────────────────────────────┘
        │ SNMP UDP 161                  │ /api/monitoring/webhook/
        │ SSH  TCP 22                   ▼
        ▼                         Django :8000
  EVE-NG 192.168.100.0/24
  ┌──────────────────────┐
  │  R1   192.168.100.1  │
  │  FW   192.168.100.2  │
  │  Core 192.168.100.10 │
  │  SW1  192.168.100.11 │
  │  SW2  192.168.100.12 │
  └──────────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Network emulation | EVE-NG Community + Cisco IOSv / IOSvL2 |
| Network automation | Netmiko 4.x, NAPALM 5.x |
| Configuration management | Ansible (playbooks in `ansible/`) |
| Metrics collection | Prometheus SNMP Exporter, Node Exporter |
| Metrics storage | Prometheus |
| Visualization | Grafana 10.x (embedded via iframe + API) |
| Alerting | Prometheus AlertManager |
| Backend | Django 4.2 + Django REST Framework 3.15 |
| Async tasks | Celery 5.4 + Redis 7.2 |
| Database | PostgreSQL 16 |
| Frontend | Bootstrap 5.3 + Grafana embeds |
| Container runtime | Docker + Docker Compose v2 |
| CI/CD | GitHub Actions |
| Security scanning | Bandit (SAST), Trivy (container), pip-audit (deps) |

---

## Project Structure

```
DevSecOpsPlatform/
├── apps/                          # Django applications
│   ├── inventory/                 # Device inventory + auto-discovery
│   ├── provisioning/              # Config templates + push + audit log
│   ├── monitoring/                # Alert ingestion + Grafana embeds
│   └── security/                  # Compliance + drift detection + RBAC
│
├── devsecops_platform/            # Django project core
│   ├── settings.py                # All configuration
│   ├── urls.py                    # Root URL routing
│   ├── celery.py                  # Celery application
│   ├── middleware.py              # Security headers middleware
│   └── context_processors.py     # Template globals
│
├── templates/                     # Django HTML templates
│   ├── base/                      # Base layout with sidebar
│   ├── inventory/
│   ├── provisioning/
│   ├── monitoring/
│   └── security/
│
├── static/                        # Static assets (CSS, JS)
│
├── prometheus/                    # Prometheus config + alert rules
│   ├── prometheus.yml
│   ├── alertmanager.yml
│   └── rules/
│       └── network_alerts.yml
│
├── snmp_exporter/                 # SNMP Exporter module config
│   └── snmp.yml
│
├── grafana/                       # Grafana provisioning
│   ├── dashboards/                # Dashboard JSON files
│   └── provisioning/
│       ├── datasources/           # Auto-configured Prometheus datasource
│       └── dashboards/            # Dashboard discovery config
│
├── ansible/                       # Ansible playbooks
│   ├── playbooks/
│   │   └── hardening.yml          # Security hardening baseline
│   └── inventory.ini              # Device inventory for Ansible
│
├── tests/                         # pytest test suite
│   ├── test_inventory.py
│   ├── test_provisioning.py
│   ├── test_monitoring.py
│   └── test_security.py
│
├── docker/
│   └── entrypoint.sh              # Container startup script
│
├── .github/
│   └── workflows/
│       └── devsecops.yml          # Full CI/CD pipeline
│
├── docker-compose.yml             # All 10 services
├── Dockerfile                     # Django/Celery image
├── requirements.txt               # Python dependencies
├── manage.py                      # Django management
├── .env                           # Local secrets (git-ignored)
├── .env.example                   # Template for .env
└── pyproject.toml                 # Bandit + coverage config
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/DevSecOpsPlatform.git
cd DevSecOpsPlatform

# 2. Create environment file
cp .env.example .env
# Edit .env and set strong passwords for production

# 3. Build and start all services
docker compose up --build -d

# 4. Watch startup logs
docker compose logs -f django

# 5. Open the platform
# http://localhost:8000  (admin / adminpassword123)
# http://localhost:3000  (Grafana — admin / grafanapassword123)
# http://localhost:9090  (Prometheus)
# http://localhost:9093  (AlertManager)
```

The startup script automatically runs migrations, seeds compliance rules, and loads Grafana fixtures.

---

## Services and Ports

| Service | Port | Description |
|---|---|---|
| Django | 8000 | Main web application and REST API |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Celery broker and result backend |
| Prometheus | 9090 | Metrics storage and query engine |
| Grafana | 3000 | Dashboards and visualization |
| AlertManager | 9093 | Alert routing and deduplication |
| SNMP Exporter | 9116 | Translates SNMP → Prometheus metrics |
| Node Exporter | 9100 | Host machine metrics |
| Celery Worker | — | Async task executor (no exposed port) |
| Celery Beat | — | Periodic task scheduler (no exposed port) |

---

## Application Modules

### Inventory (`apps/inventory/`)
- Full CRUD for network devices
- Auto-discovery: ICMP ping → SNMP sysName → DNS → register
- Per-device reachability checks
- REST API with filtering, search, ordering
- [Full documentation →](apps/inventory/README.md)

### Provisioning (`apps/provisioning/`)
- Jinja2 configuration templates (VLANs, interfaces, ACLs, OSPF, hardening)
- Async SSH push via Netmiko + Celery
- Template preview endpoint (render without pushing)
- Immutable audit log for every config action
- [Full documentation →](apps/provisioning/README.md)

### Monitoring (`apps/monitoring/`)
- AlertManager webhook receiver — ingests firing/resolved alerts
- Grafana dashboard embed registry
- Alert acknowledgment
- Main dashboard with device status and Grafana iframe
- [Full documentation →](apps/monitoring/README.md)

### Security & Compliance (`apps/security/`)
- 8 built-in compliance rules (SSH v2, Telnet disabled, SNMP v3, ACL, etc.)
- Config snapshot and golden-config drift detection
- Unified diff view for drifted configs
- Role-based access control (Admin, Network Engineer, Read-Only)
- [Full documentation →](apps/security/README.md)

---

## Network Topology

```
Internet (Cloud)
       │
  [R1 - Edge Router]     192.168.100.1   Cisco IOSv
       │
  [FW - Firewall]        192.168.100.2   ASAv / pfSense
       │
  [Core-SW]              192.168.100.10  Cisco IOSvL2 (L3 + SVIs)
    /       \
[SW1]      [SW2]         192.168.100.11/12   Cisco IOSvL2 (Access)
  │            │
[PC1]       [PC2]        VPCS / Alpine Linux

VLANs:
  VLAN 10  — Users       (10.0.10.0/24)
  VLAN 20  — Servers     (10.0.20.0/24)
  VLAN 99  — Management  (192.168.100.0/24)

Routing: OSPF between all routers/L3 switches
SSH:     v2 only, management VLAN only
SNMP:    v2c (read) + v3 (preferred)
```

---

## Data Flow

```
Browser Request
      │
      ▼
Django (UI + REST API)
      │                         │
      ▼                         ▼
Celery Task Queue          Grafana iframe
(Redis broker)             src=localhost:3000
      │
      ├─── provisioning queue ──► SSH via Netmiko ──► Network device
      ├─── discovery queue   ──► ICMP ping + SNMP  ──► Subnet scan
      └─── compliance queue  ──► SSH show commands ──► Compliance check

Prometheus scrape loop (every 30s)
      │
      ├──► SNMP Exporter :9116 ──► Devices via SNMP UDP 161
      └──► Node Exporter :9100 ──► Host metrics

AlertManager ──► POST /api/monitoring/webhook/alertmanager/ ──► Alert model
```

---

## Authentication and RBAC

### JWT Authentication

All API endpoints require a Bearer token:

```bash
# Obtain token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "adminpassword123"}'

# Use token
curl http://localhost:8000/api/inventory/devices/ \
  -H "Authorization: Bearer <access_token>"

# Refresh token
curl -X POST http://localhost:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

Tokens expire after 60 minutes (access) and 7 days (refresh).

### Roles

| Role | Read | Push Config | Compliance | User Management |
|---|---|---|---|---|
| `read_only` | Yes | No | No | No |
| `network_engineer` | Yes | Yes | Yes | No |
| `admin` | Yes | Yes | Yes | Yes |

Assign roles via: `http://localhost:8000/admin/` → User Profiles

---

## Environment Variables

See [.env.example](.env.example) for all variables. Critical ones:

| Variable | Description | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key — change in production | required |
| `DJANGO_DEBUG` | Debug mode — set `False` in production | `True` |
| `POSTGRES_PASSWORD` | Database password | required |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | required |
| `GRAFANA_URL` | Browser-facing Grafana URL for iframes | `http://localhost:3000` |
| `MANAGEMENT_SUBNET` | EVE-NG management subnet for discovery | `192.168.100.0/24` |
| `SNMP_COMMUNITY` | Default SNMP community string | `public` |

---

## CI/CD Pipeline

Every push to `main` or `develop` triggers:

```
push → lint → bandit → pip-audit → test → [trivy] → build+push → deploy
```

| Job | Tool | On failure |
|---|---|---|
| Lint | yamllint, ansible-lint | Blocks merge |
| SAST | Bandit | Uploads artifact, non-blocking |
| Dependencies | pip-audit | Uploads artifact, non-blocking |
| Container scan | Trivy → SARIF | Visible in Security tab |
| Tests | pytest + PostgreSQL | Blocks merge |
| Build | Docker buildx → GHCR | On main only |
| Deploy | SSH to staging | On main only |

See [.github/workflows/README.md](.github/workflows/README.md) for full details.

---

## Development Workflow

```bash
# Rebuild after changing Python code
docker compose up --build -d django celery celery_beat

# Run tests
docker compose exec django pytest -v

# Open Django shell
docker compose exec django python manage.py shell

# Check Celery tasks
docker compose exec django celery -A devsecops_platform inspect active

# View all logs
docker compose logs -f

# Reset everything
docker compose down -v && docker compose up --build -d
```

---

## Component READMEs

| Component | README |
|---|---|
| Inventory App | [apps/inventory/README.md](apps/inventory/README.md) |
| Provisioning App | [apps/provisioning/README.md](apps/provisioning/README.md) |
| Monitoring App | [apps/monitoring/README.md](apps/monitoring/README.md) |
| Security App | [apps/security/README.md](apps/security/README.md) |
| Django Core | [devsecops_platform/README.md](devsecops_platform/README.md) |
| Prometheus | [prometheus/README.md](prometheus/README.md) |
| SNMP Exporter | [snmp_exporter/README.md](snmp_exporter/README.md) |
| Grafana | [grafana/README.md](grafana/README.md) |
| Ansible | [ansible/README.md](ansible/README.md) |
| CI/CD Pipeline | [.github/workflows/README.md](.github/workflows/README.md) |
| Tests | [tests/README.md](tests/README.md) |
| Docker | [docker/README.md](docker/README.md) |

---

## License

MIT License — see LICENSE file for details.
