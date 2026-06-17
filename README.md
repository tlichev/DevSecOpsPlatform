# DevSecOps Platform — Network Infrastructure Automation

A production-ready **DevSecOps platform** for centralized management, monitoring, provisioning, and security compliance enforcement of Cisco network devices across a three-site enterprise network emulated in **EVE-NG**.

Inspired by **Cisco DNA Center (DNAC)** — built entirely with open-source tools.

---

## Table of Contents

1. [Concept & Goals](#1-concept--goals)
2. [Network Topology](#2-network-topology)
3. [IP Addressing](#3-ip-addressing)
4. [Firewall High Availability](#4-firewall-high-availability)
5. [Site-to-Site IPSec VPN](#5-site-to-site-ipsec-vpn)
6. [Routing](#6-routing)
7. [System Architecture](#7-system-architecture)
8. [Technology Stack](#8-technology-stack)
9. [Docker Services](#9-docker-services)
10. [Django Applications](#10-django-applications)
11. [Data Flows](#11-data-flows)
12. [API Reference](#12-api-reference)
13. [Security Design](#13-security-design)
14. [CI/CD Pipeline](#14-cicd-pipeline)
15. [Quick Start](#15-quick-start)
16. [Project Structure](#16-project-structure)

---

## 1. Concept & Goals

Modern enterprise networks require more than manual CLI work. This platform provides a **single pane of glass** for network operations teams:

| Capability | Description |
|---|---|
| **Inventory** | Central database of all devices with real-time ICMP/SNMP status |
| **CLI Console** | Browser-based interactive SSH terminal (xterm.js + WebSocket) |
| **Provisioning** | Push Jinja2 config templates to devices via SSH with before/after diff |
| **Config Pull** | Download a device's full running-config as a `.txt` file in one click |
| **Monitoring** | Prometheus + Grafana dashboards; AlertManager webhook receiver |
| **Compliance** | 12 regex-based security rules evaluated against live running-configs |
| **Drift Detection** | Compare golden baseline configs against actual device configs |
| **RBAC** | Three roles (Admin / Engineer / Read-Only) enforced on UI and REST API |
| **2FA** | Email-based OTP for every login; cryptographically secure, 10-minute expiry |
| **Audit Trail** | Every config push logged with rendered config, diff, status, and executor |

---

## 2. Network Topology

Three-site enterprise network emulated in **EVE-NG** (Cisco IOL + ASAv), connected via Site-to-Site IPSec VPN through a simulated ISP zone.

```
                    ┌─────────────────────────────────┐
                    │         ISP ZONE (WAN)           │
                    │  SW-Sofia   SW-Plovdiv  SW-Burgas │
                    │  4.2.2.1    4.2.2.33    4.2.2.65  │
                    └──────┬──────────┬──────────┬──────┘
                           │ IPSec    │ IPSec    │ IPSec
               ┌───────────┘  (full   └─────┐    └──────────────┐
               │              mesh)         │                    │
   ┌───────────┴──────────┐   ┌─────────────┴────────┐  ┌───────┴─────────────┐
   │      SOFIA (HQ)      │   │       PLOVDIV         │  │       BURGAS         │
   │──────────────────────│   │──────────────────────│  │──────────────────────│
   │ Sofia-PRIM  4.2.2.2  │   │ Plovdiv-PRIM 4.2.2.41│  │ Burgas-PRIM 4.2.2.81 │
   │ Sofia-SEC   4.2.2.3  │   │ Plovdiv-SEC  4.2.2.42│  │ Burgas-SEC  4.2.2.82 │
   │ VIP         4.2.2.4  │   │ VIP          4.2.2.43│  │ VIP         4.2.2.83 │
   │ LAN  172.16.1.0/29   │   │ LAN   172.16.2.0/29  │  │ LAN   172.16.3.0/29  │
   │ R-Sofia   .1.4       │   │ R-Plovdiv    .2.4    │  │ R-Burgas    .3.4     │
   │ L2S-Sofia            │   │ L2S-Plovdiv          │  │ L2S-Burgas           │
   └──────────────────────┘   └──────────────────────┘  └──────────────────────┘
```

**15 devices total — 5 per site:**

| Site | Device | Role | Image |
|------|--------|------|-------|
| Sofia | Sofia-PRIM | Primary Firewall (Active) | Cisco ASAv |
| Sofia | Sofia-SEC | Secondary Firewall (Standby) | Cisco ASAv |
| Sofia | SW-Sofia | ISP L3 Switch | Cisco IOL L3 |
| Sofia | L2S-Sofia | LAN L2 Switch | Cisco IOL L2 |
| Sofia | R-Sofia | Edge Router | Cisco IOL L3 |
| Plovdiv | Plovdiv-PRIM | Primary Firewall (Active) | Cisco ASAv |
| Plovdiv | Plovdiv-SEC | Secondary Firewall (Standby) | Cisco ASAv |
| Plovdiv | SW-Plovdiv | ISP L3 Switch | Cisco IOL L3 |
| Plovdiv | L2S-Plovdiv | LAN L2 Switch | Cisco IOL L2 |
| Plovdiv | R-Plovdiv | Edge Router | Cisco IOL L3 |
| Burgas | Burgas-PRIM | Primary Firewall (Active) | Cisco ASAv |
| Burgas | Burgas-SEC | Secondary Firewall (Standby) | Cisco ASAv |
| Burgas | SW-Burgas | ISP L3 Switch | Cisco IOL L3 |
| Burgas | L2S-Burgas | LAN L2 Switch | Cisco IOL L2 |
| Burgas | R-Burgas | Edge Router | Cisco IOL L3 |

---

## 3. IP Addressing

### WAN (Outside) interfaces — `/27` per site

| Device | IP | Subnet | Role |
|--------|----|--------|------|
| SW-Sofia | 4.2.2.1 | 4.2.2.0/27 | ISP gateway — Sofia |
| Sofia-PRIM outside | 4.2.2.2 | 4.2.2.0/27 | Active firewall WAN |
| Sofia-SEC outside | 4.2.2.3 | 4.2.2.0/27 | Standby firewall WAN |
| **Sofia Failover VIP** | **4.2.2.4** | 4.2.2.0/27 | IPSec tunnel source |
| SW-Plovdiv | 4.2.2.33 | 4.2.2.32/27 | ISP gateway — Plovdiv |
| Plovdiv-PRIM outside | 4.2.2.41 | 4.2.2.32/27 | Active firewall WAN |
| Plovdiv-SEC outside | 4.2.2.42 | 4.2.2.32/27 | Standby firewall WAN |
| **Plovdiv Failover VIP** | **4.2.2.43** | 4.2.2.32/27 | IPSec tunnel source |
| SW-Burgas | 4.2.2.65 | 4.2.2.64/27 | ISP gateway — Burgas |
| Burgas-PRIM outside | 4.2.2.81 | 4.2.2.64/27 | Active firewall WAN |
| Burgas-SEC outside | 4.2.2.82 | 4.2.2.64/27 | Standby firewall WAN |
| **Burgas Failover VIP** | **4.2.2.83** | 4.2.2.64/27 | IPSec tunnel source |

### LAN (Inside) interfaces — `/29` per site

| Site | Subnet | Gateway VIP | PRIM IP | SEC IP | Router IP |
|------|--------|-------------|---------|--------|-----------|
| Sofia | 172.16.1.0/29 | 172.16.1.1 | 172.16.1.2 | 172.16.1.3 | 172.16.1.4 |
| Plovdiv | 172.16.2.0/29 | 172.16.2.1 | 172.16.2.2 | 172.16.2.3 | 172.16.2.4 |
| Burgas | 172.16.3.0/29 | 172.16.3.1 | 172.16.3.2 | 172.16.3.3 | 172.16.3.4 |

### Failover link addresses

| Site | Failover Link | PRIM | SEC | State Link | PRIM | SEC |
|------|---------------|------|-----|------------|------|-----|
| Sofia | 10.0.0.0/30 | 10.0.0.1 | 10.0.0.2 | 10.0.0.4/30 | 10.0.0.5 | 10.0.0.6 |
| Plovdiv | 10.0.1.0/30 | 10.0.1.1 | 10.0.1.2 | 10.0.1.4/30 | 10.0.1.5 | 10.0.1.6 |
| Burgas | 10.0.2.0/30 | 10.0.2.1 | 10.0.2.2 | 10.0.2.4/30 | 10.0.2.5 | 10.0.2.6 |

### Loopback addresses

| Device | Loopback IP | Usage |
|--------|-------------|-------|
| R-Sofia | 110.0.0.1/32 | Router ID, reachability |
| R-Plovdiv | 120.0.0.1/32 | Router ID, reachability |
| R-Burgas | 130.0.0.1/32 | Router ID, reachability |

### Management network (planned)

| Device | Management IP | Interface | Protocol |
|--------|--------------|-----------|----------|
| Sofia-PRIM | 192.168.1.10 | Gi0/3 | SSH v2 |
| Sofia-SEC | 192.168.1.11 | Gi0/3 | SSH v2 |
| Plovdiv-PRIM | 192.168.1.20 | Gi0/3 | SSH v2 |
| Plovdiv-SEC | 192.168.1.21 | Gi0/3 | SSH v2 |
| Burgas-PRIM | 192.168.1.30 | Gi0/3 | SSH v2 |
| Burgas-SEC | 192.168.1.31 | Gi0/3 | SSH v2 |
| SW-Sofia / SW-Plovdiv / SW-Burgas | 192.168.1.40–42 | Eth0/3 | SSH v2 |
| R-Sofia / R-Plovdiv / R-Burgas | 192.168.1.50–52 | Loopback | SSH v2 |
| Django server | 192.168.1.100 | Host | Netmiko/NAPALM |

---

## 4. Firewall High Availability

Each site has a pair of **Cisco ASAv** firewalls in **Active/Standby** mode. Only the Primary (Active) unit forwards traffic. The Secondary (Standby) unit synchronises configuration and connection state in real time and takes over within seconds if Primary fails.

### Interface mapping

| Interface | Role | Connection |
|-----------|------|------------|
| GigabitEthernet0/0 | outside (WAN) | → ISP switch |
| GigabitEthernet0/1 | inside (LAN) | → L2S switch |
| GigabitEthernet0/2 | failover link | Direct PRIM ↔ SEC (heartbeat + config sync) |
| GigabitEthernet0/3 | management | Planned phase 2 |
| GigabitEthernet0/4 | stateful link | Direct PRIM ↔ SEC (connection table sync) |
| GigabitEthernet0/5–7 | reserved | DMZ, future expansion |

### Failover behaviour

- Heartbeat runs on `Gi0/2`. Loss of heartbeat → SEC acquires VIP addresses within seconds
- Configuration replicates automatically from PRIM to SEC on every change
- IPSec tunnels always source from the **Failover VIP** — tunnel survives a failover transparently

### ASAv security levels

| Interface | Security Level | Policy |
|-----------|---------------|--------|
| outside | 0 | Lowest trust — internet |
| management | 50 | Medium trust — management access |
| inside | 100 | Full trust — internal LAN |

### Outside ACL

Only IPSec-related traffic is permitted inbound from the WAN:

| Action | Protocol | Port | Reason |
|--------|----------|------|--------|
| PERMIT | ESP | — | IPSec payload |
| PERMIT | UDP | 500 | IKEv2 negotiation |
| PERMIT | UDP | 4500 | IKEv2 NAT-T |
| DENY | IP | any | Everything else (logged) |

---

## 5. Site-to-Site IPSec VPN

All three sites are connected in a **full mesh** of IPSec IKEv2 L2L tunnels. Each site maintains two tunnels — one to each of the other sites. Tunnels always source and terminate on the **Failover VIP**.

### Tunnel matrix

| Tunnel | Source VIP | Destination VIP | Protected traffic |
|--------|-----------|-----------------|-------------------|
| Sofia → Plovdiv | 4.2.2.4 | 4.2.2.43 | 172.16.1.0/29 ↔ 172.16.2.0/29 |
| Sofia → Burgas | 4.2.2.4 | 4.2.2.83 | 172.16.1.0/29 ↔ 172.16.3.0/29 |
| Plovdiv → Sofia | 4.2.2.43 | 4.2.2.4 | 172.16.2.0/29 ↔ 172.16.1.0/29 |
| Plovdiv → Burgas | 4.2.2.43 | 4.2.2.83 | 172.16.2.0/29 ↔ 172.16.3.0/29 |
| Burgas → Sofia | 4.2.2.83 | 4.2.2.4 | 172.16.3.0/29 ↔ 172.16.1.0/29 |
| Burgas → Plovdiv | 4.2.2.83 | 4.2.2.43 | 172.16.3.0/29 ↔ 172.16.2.0/29 |

### IKEv2 parameters

| Parameter | Value |
|-----------|-------|
| IKE version | IKEv2 |
| Encryption | AES-256 |
| Integrity | SHA-256 |
| DH group | Group 14 (2048-bit) |
| PRF | SHA-256 |
| IKE lifetime | 86400 s (24 h) |
| ESP encryption | AES-256 |
| ESP integrity | SHA-256 |
| Authentication | Pre-shared key |
| Tunnel type | IPSec L2L (crypto map) |

### NAT policy

Inter-site traffic is excluded from NAT via identity NAT rules (higher priority than dynamic NAT):

- **NAT rule 1** — LAN-A ↔ LAN-B (no translation)
- **NAT rule 2** — LAN-A ↔ LAN-C (no translation)
- **NAT after-auto** — LAN → Internet (dynamic PAT to outside interface)

---

## 6. Routing

All routing is **static**. Firewalls know the remote LAN subnets and point them at the IPSec peer VIP. Edge routers have a single default route pointing at the inside firewall VIP.

### Firewall static routes

| Firewall | Destination | Next Hop | Description |
|----------|-------------|----------|-------------|
| Sofia-PRIM | 0.0.0.0/0 | 4.2.2.1 | Default → ISP |
| Sofia-PRIM | 172.16.2.0/29 | 4.2.2.43 | Plovdiv LAN via IPSec |
| Sofia-PRIM | 172.16.3.0/29 | 4.2.2.83 | Burgas LAN via IPSec |
| Plovdiv-PRIM | 0.0.0.0/0 | 4.2.2.33 | Default → ISP |
| Plovdiv-PRIM | 172.16.1.0/29 | 4.2.2.4 | Sofia LAN via IPSec |
| Plovdiv-PRIM | 172.16.3.0/29 | 4.2.2.83 | Burgas LAN via IPSec |
| Burgas-PRIM | 0.0.0.0/0 | 4.2.2.65 | Default → ISP |
| Burgas-PRIM | 172.16.1.0/29 | 4.2.2.4 | Sofia LAN via IPSec |
| Burgas-PRIM | 172.16.2.0/29 | 4.2.2.43 | Plovdiv LAN via IPSec |

### Edge router static routes

| Router | Destination | Next Hop |
|--------|-------------|----------|
| R-Sofia | 0.0.0.0/0 | 172.16.1.1 (firewall VIP) |
| R-Plovdiv | 0.0.0.0/0 | 172.16.2.1 (firewall VIP) |
| R-Burgas | 0.0.0.0/0 | 172.16.3.1 (firewall VIP) |

---

## 7. System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       Docker Compose Stack                          │
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │ Browser  │───▶│    Django    │───▶│        SQLite          │   │
│  │ (xterm.js│    │  (Gunicorn)  │    │      (WAL mode)        │   │
│  │  WS/HTTP)│    │   port 8000  │    └────────────────────────┘   │
│  └──────────┘    └──────┬───────┘                                  │
│         │  WebSocket    │                                           │
│         │  /ws/cli/<pk> │                                           │
│  ┌──────┴──────┐        │                                           │
│  │ Django      │   ┌────┴────────────────────┐                     │
│  │ Channels    │   │  Celery Workers          │                     │
│  │ (ASGI)      │   │  queues: provisioning    │                     │
│  └──────┬──────┘   │          monitoring      │                     │
│         │          │          discovery       │                     │
│   Paramiko SSH     │          default         │                     │
│         │          └────────────┬────────────┘                     │
│         │               ┌───────┴──────┐                           │
│         │               │    Redis     │                           │
│         │               │  broker +    │                           │
│         │               │  cache +     │                           │
│         │               │  task results│                           │
│         │               └──────────────┘                           │
│         │                                                           │
│   ┌─────┴───────────────────────────────────────┐                  │
│   │          Observability Stack                  │                 │
│   │  Prometheus:9090  Grafana:3000               │                 │
│   │  AlertManager:9093  SNMP Exporter:9116       │                 │
│   │  Node Exporter:9100                          │                 │
│   └──────────────────────────────────────────────┘                 │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ SSH + SNMP
            ┌──────────────────┴──────────────────────┐
            │        EVE-NG Network (3 sites)          │
            │  Sofia       Plovdiv       Burgas         │
            │  172.16.1.0  172.16.2.0   172.16.3.0    │
            │  /29         /29          /29            │
            └──────────────────────────────────────────┘
```

**Config push flow:**
1. Engineer submits push request via UI
2. Django validates and enqueues a Celery task on `provisioning` queue
3. Worker SSHes to device via Netmiko → captures `show running-config` (before)
4. Sends rendered config lines via `send_config_set()` → `save_config()`
5. Captures `show running-config` (after) → computes unified diff
6. Stores diff + status in `AuditLog`; browser polls task status every 2 s

---

## 8. Technology Stack

### Backend

| Component | Technology | Version |
|---|---|---|
| Web framework | Django | 4.2 |
| REST API | Django REST Framework | 3.15 |
| WebSocket | Django Channels (ASGI) | 4.x |
| Authentication | Session (UI) + JWT (API) | — |
| 2FA | Email OTP via Celery task | — |
| Task queue | Celery | 5.3 |
| Message broker | Redis | 7 |
| Database | SQLite (WAL mode) | Built-in |
| SSH automation | Netmiko (tasks) + Paramiko (WebSocket) | — |
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
| Fonts | Inter (UI), JetBrains Mono (code/terminal) |
| Terminal emulator | xterm.js (WebSocket → Paramiko SSH) |
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

## 9. Docker Services

The entire stack runs as **9 containers**:

| Service | Port | Role |
|---------|------|------|
| `django` | 8000 | Web UI + REST API + WebSocket (Gunicorn + Daphne) |
| `celery` | — | Async task workers (4 queues) |
| `celery-beat` | — | Periodic task scheduler |
| `redis` | 6379 | Celery broker + result backend + Django cache |
| `prometheus` | 9090 | Metrics scraper (30-day retention) |
| `snmp_exporter` | 9116 | Translates SNMP → Prometheus metrics |
| `node_exporter` | 9100 | Host OS metrics |
| `grafana` | 3000 | Dashboard UI |
| `alertmanager` | 9093 | Routes Prometheus alerts → Django webhook |

### Celery task queues

| Queue | App | Tasks |
|-------|-----|-------|
| `discovery` | Inventory | ICMP polling, SNMP discovery, device status |
| `provisioning` | Provisioning | SSH config push, running-config pull |
| `monitoring` | Monitoring | Alert sync, device-down reconciliation |
| `default` | Accounts, Security | OTP email, compliance checks, drift detection |

### Periodic tasks (Celery Beat)

| Task | Schedule | Purpose |
|------|----------|---------|
| `poll-all-devices` | Every 5 min | ICMP + SNMP poll all devices |
| `sync-prometheus-alerts` | Every 2 min | Reconcile alerts from Prometheus API |
| `mark-devices-from-alerts` | Every 3 min | Sync device status from active alerts |
| `daily-compliance-check` | 02:00 | Run all compliance rules on all UP devices |
| `daily-drift-check` | 03:00 | Golden config drift on all UP devices |

---

## 10. Django Applications

### `apps/accounts` — Authentication, 2FA & RBAC

→ [Full README](apps/accounts/README.md)

**Models:** `User` (AbstractUser + role + avatar), `TwoFactorCode` (6-digit OTP, 10-min expiry)

**Roles:**

| Role | Permissions |
|------|-------------|
| `admin` | Full access including user management |
| `engineer` | Read/write devices, push configs, run checks |
| `readonly` | View-only across all apps |

**Two-factor authentication flow:**
1. User submits username + password → credentials validated
2. Users with no email skip 2FA and log in directly
3. Users with email → 6-digit OTP generated with `secrets.randbelow()`, emailed via Celery
4. Pre-auth state stored in session (`pre_auth_user_id`, `pre_auth_backend`, `pre_auth_next`)
5. User enters code at `/accounts/verify-otp/` → `login()` called → redirect

**Security controls:** 5-attempt lockout, 60 s resend cooldown (server + client), 20 req/min rate limit on OTP verification, email displayed as `t***@gmail.com`.

**Decorators:** `@admin_required`, `@engineer_required` for view-level RBAC.

---

### `apps/inventory` — Device Inventory & Discovery

→ [Full README](apps/inventory/README.md)

**Model: `Device`** — all 15 EVE-NG devices registered here with management IPs, site, device type, SNMP community, and Fernet-encrypted SSH credentials.

**SSH credential security:** Fernet AES encryption at rest. Key derived from `FIELD_ENCRYPTION_KEY` env var (SHA-256 fallback from `SECRET_KEY`). Decrypted only inside Celery workers at SSH connection time — never returned by the API.

**Celery tasks:**
- `poll_device(id)` — ICMP ping → `mark_seen()` or `mark_down()`
- `poll_all_devices()` — Parallel Celery `group` for all devices
- `discover_network()` — Scans `MGMT_NETWORK` CIDR, creates new Device records for unknown live hosts via SNMP `sysName`

**REST API:** `DeviceViewSet` with custom actions `poll`, `poll_all`, `discover`, `status_list`, `by_site`. Standalone `dashboard_stats` endpoint feeds the dashboard counters.

---

### `apps/provisioning` — Config Push, File Templates & Config Pull

→ [Full README](apps/provisioning/README.md)

**Models:** `ProvisioningTemplate` (DB-stored Jinja2 templates), `AuditLog` (immutable push + pull history)

**Template engine:** Dual-loader Jinja2 environment — DB templates take priority over file templates. 9 built-in `.j2` files in `config_templates/`:

| Template | Purpose |
|----------|---------|
| `ssh_hardening.j2` | SSH v2, disable Telnet/HTTP, AAA, password policy |
| `ospf_area0.j2` | OSPF process, area 0, passive interfaces |
| `router_ospf_loopback.j2` | Loopback + OSPF redistribute connected |
| `firewall_primary_wan.j2` | WAN ACL and NAT rules for ASAv |
| `ntp_syslog.j2` | NTP server, timezone, syslog destination |
| `snmp_v2c.j2` | SNMPv2c community, location, contact, trap host |
| `acl_management.j2` | Management ACL (permit 192.168.1.0/24 only) |
| `interface_descriptions.j2` | Interface descriptions per device type |
| `vlan_access.j2` | Access-port VLAN + spanning-tree portfast |

**File template management UI** (`/provisioning/file-templates/`):
- Create / edit / delete `.j2` files via a browser editor
- Jinja2 syntax validated before saving — broken templates are rejected with the error line
- Variable chip sidebar inserts `{{ variable }}` at cursor
- Filenames validated against `^[a-z0-9_\-]+$` — no path traversal possible

**Config push flow:**
```
POST /api/provisioning/push/ { device_ids, template_name, dry_run }
  └── Celery: push_config_to_device
        ├── Render Jinja2 template
        ├── Netmiko SSH → show running-config (before)
        ├── send_config_set() → save_config()
        ├── show running-config (after)
        ├── unified_diff(before, after) → AuditLog
        └── Browser polls /api/provisioning/task/<id>/ every 2 s
```

**Running-config pull + download:**
```
[Pull Config] button → POST /api/provisioning/pull-config/
  └── Celery: pull_running_config
        └── Netmiko SSH → show running-config → AuditLog
  Browser polls → state=SUCCESS → GET /provisioning/pull-config/<task_id>/download/
  → sofia_sofia-prim_running-config_2026-06-17_23-47.txt (attachment)
```

---

### `apps/cli` — Browser SSH Terminal

→ [Full README](apps/cli/README.md)

**Two parallel interfaces:**

| Interface | Technology | Use case |
|-----------|-----------|---------|
| WebSocket terminal | Django Channels + Paramiko | Interactive shell, full PTY |
| REST + Celery | Netmiko task | Scripted command execution with DB history |

**WebSocket terminal** at `/inventory/<pk>/cli/`:
- xterm.js with JetBrains Mono, dark theme, 5000-line scrollback
- `SSHConsumer` opens a Paramiko `invoke_shell()` PTY (`xterm-256color`, 220×50)
- Bidirectional proxy: keyboard input → WebSocket → SSH channel; SSH output → WebSocket → terminal
- Terminal resize events sent as `{ type: "resize", cols, rows }` → `channel.resize_pty()`
- Engineer role required; WebSocket closed with code 4403 if unauthorized

**REST command API** at `/api/cli/execute/`:
- Commands routed to `send_config_set()` for config-mode commands, `send_command()` for exec-mode
- Every command saved as a `CLICommand` record with output, duration, and error flag
- Session history accessible at `/api/cli/sessions/<id>/history/`

---

### `apps/monitoring` — Alerts & Dashboards

→ [Full README](apps/monitoring/README.md)

**Models:** `Alert` (deduplicated by `fingerprint`), `AlertNotification` (email delivery log)

**AlertManager webhook** at `POST /api/alerts/webhook/` (no auth, network-isolated):
- `update_or_create(fingerprint=...)` — repeat alerts update the existing record
- `DeviceDown` alerts instantly set `device.status = 'down'` in inventory
- AlertManager inhibition rules suppress downstream `InterfaceDown` / `HighInterfaceErrors` alerts when a device is down (prevents alert storms)

**8 Prometheus alert rules:** `DeviceDown`, `InterfaceDown`, `HighCPULoad`, `HighMemoryUsage`, `HighInterfaceErrors`, `BGPPeerDown`, `OSPFNeighborLost`, `SNMPUnreachable`

**Email notifications:** Celery task `send_alert_email` on `critical` alerts — rendered HTML email with severity badge and device info.

---

### `apps/security` — Compliance & Drift Detection

**Models:** `ComplianceRule`, `ComplianceResult`, `GoldenConfig`, `DriftResult`

**12 built-in compliance rules** evaluated by regex against live running-configs:

| Rule | Severity | Check type |
|------|----------|-----------|
| SSH v2 enabled | Critical | Presence |
| Telnet disabled | Critical | Absence |
| AAA new-model | Critical | Presence |
| No enable password | Critical | Absence |
| NTP server configured | Warning | Presence |
| SNMP community with ACL | Warning | Presence |
| Syslog host configured | Warning | Presence |
| Service password-encryption | Warning | Presence |
| OSPF MD5 authentication | Warning | Presence (routers only) |
| CDP disabled on firewalls | Warning | Absence (firewalls only) |
| Login banner present | Info | Presence |
| Service timestamps log | Info | Presence |

**Compliance score:** `(pass_count / applicable_rules) × 100`. Device is compliant at ≥ 80%.

**Drift detection:** `show running-config` via SSH → `difflib.unified_diff(golden, actual)` → count `+/-` lines → `DriftResult`. Displayed with green/red/blue syntax colouring.

---

## 11. Data Flows

### SNMP polling loop
```
Celery Beat (every 5 min)
  └── poll_all_devices()
        └── poll_device(id) [discovery queue, parallel group]
              ├── ICMP ping
              ├── success → device.mark_seen() → status=up
              └── failure → device.mark_down() → status=down
```

### Prometheus alert pipeline
```
Device unreachable
  └── Prometheus fires alert rule (rules/alerts.yml)
        └── AlertManager routes + inhibits
              └── POST /api/alerts/webhook/
                    ├── Alert.update_or_create(fingerprint=...)
                    ├── DeviceDown? → Device.update(status='down')
                    └── send_alert_email.delay() [critical alerts]
```

### 2FA login flow
```
POST /accounts/login/
  ├── authenticate() → user found, has email
  ├── TwoFactorCode.generate_for(user) [cryptographically secure]
  ├── send_otp_email.apply_async() [default queue]
  ├── session['pre_auth_user_id'] = user.pk
  └── redirect → /accounts/verify-otp/
        └── POST code → otp.is_valid() → login() → redirect(next)
```

### Running-config download
```
[Pull Config] button
  └── POST /api/provisioning/pull-config/ { device_id }
        └── pull_running_config.apply_async() [provisioning queue]
              └── Netmiko SSH → show running-config → AuditLog
  Browser polls /api/provisioning/task/<id>/ every 2 s
  → SUCCESS → GET /provisioning/pull-config/<task_id>/download/
  → sofia_r-sofia_running-config_2026-06-17_23-47.txt
```

---

## 12. API Reference

Base URL: `http://localhost:8000/api/`  
Interactive docs: `http://localhost:8000/api/docs/` (Swagger UI)

### Authentication
```
POST /api/token/          → { access, refresh }   (JWT, role in claims)
POST /api/token/refresh/  → { access }
POST /api/token/verify/   → 200 OK if valid
```

### Inventory
```
GET    /api/devices/                    → List (filter: site, status, device_type)
POST   /api/devices/                    → Create (engineer+)
GET    /api/devices/{id}/               → Detail
PATCH  /api/devices/{id}/               → Update (engineer+)
DELETE /api/devices/{id}/               → Delete (admin)
POST   /api/devices/{id}/poll/          → Trigger ICMP poll
POST   /api/devices/poll_all/           → Poll all devices
POST   /api/devices/discover/           → Network discovery scan
GET    /api/devices/status_list/        → Minimal list for topology.js
GET    /api/devices/by_site/?site=sofia → Filter by site
GET    /api/inventory/dashboard-stats/  → Dashboard counters
```

### Provisioning
```
GET    /api/provisioning/templates/          → List DB templates
POST   /api/provisioning/templates/          → Create (engineer+)
POST   /api/provisioning/render/             → Preview render (no SSH)
POST   /api/provisioning/push/               → Push config to device(s)
POST   /api/provisioning/pull-config/        → Pull running-config
GET    /api/provisioning/task/{task_id}/     → Poll task state + result
GET    /api/provisioning/audit/              → Audit log
GET    /api/provisioning/audit/{id}/         → Audit entry detail
```

### CLI
```
GET    /api/cli/sessions/                    → List sessions (filter by device)
POST   /api/cli/sessions/                    → Create session
GET    /api/cli/sessions/{id}/history/       → Command history
POST   /api/cli/execute/                     → Run command (async)
GET    /api/cli/task/{task_id}/              → Poll command result
WS     /ws/cli/{device_pk}/                  → Live SSH terminal
```

### Monitoring
```
POST /api/alerts/webhook/                       → AlertManager receiver (no auth)
GET  /api/monitoring/alerts/                    → List alerts (filter: severity, status, site)
POST /api/monitoring/alerts/{id}/acknowledge/   → Acknowledge alert
GET  /api/monitoring/alerts/active-summary/     → Count by severity
```

### Security
```
GET  /api/security/rules/                       → Compliance rules
GET  /api/security/results/                     → Compliance results
GET  /api/security/compliance/summary/          → Per-device scores
POST /api/security/compliance/run/{device_id}/  → Run checks on one device
POST /api/security/compliance/run-all/          → Run checks on all UP devices
POST /api/security/drift/run/{device_id}/       → Drift check
GET  /api/security/golden/                      → Golden config baselines
GET  /api/security/drift/                       → Drift results
```

---

## 13. Security Design

### Authentication layers

| Layer | Method | TTL |
|-------|--------|-----|
| Web UI | Django sessions | 8 hours |
| REST API | JWT (SimpleJWT) | Access: 8 h / Refresh: 7 days |
| 2FA | Email OTP (`secrets.randbelow`) | 10 minutes |

### Credential protection
- SSH passwords are **Fernet-encrypted** at rest — never stored or logged in plaintext
- Encryption key in `FIELD_ENCRYPTION_KEY` env var; derived from `SECRET_KEY` via SHA-256 if absent
- REST API marks `ssh_password` as `write_only` — never returned in responses
- OTP codes generated with `secrets.randbelow(1_000_000)` — cryptographically secure PRNG

### Rate limiting
- Login: **10 POST/min per IP** (`django-ratelimit` → Redis)
- OTP verification: **20 POST/min per IP**
- OTP lockout: **5 failed attempts** clears session and forces re-login
- OTP resend: **60-second server-side cooldown** (also enforced client-side via `localStorage`)

### Network security (ASAv)
- Outside ACL permits only ESP + UDP/500 + UDP/4500 — all other inbound traffic denied and logged
- Inter-site traffic uses identity NAT (no address translation)
- IPSec with AES-256 / SHA-256 / Group 14 — no legacy algorithms

### HTTP security headers (production)

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` |
| `Content-Security-Policy` | `default-src 'self'; frame-src 'self' <grafana>; object-src 'none'` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-Content-Type-Options` | `nosniff` |

---

## 14. CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/devsecops.yml`) — 5 parallel jobs:

```
push to main / PR
  ├── lint       → flake8 (max 120 chars, excludes migrations)
  ├── bandit     → Python SAST — fails on HIGH severity
  ├── pip-audit  → Dependency CVE scan — fails on any known vuln
  ├── test       → Django unit tests + coverage ≥ 50%
  └── trivy      → Container scan (needs: test) — fails on CRITICAL CVEs
```

All scan reports uploaded as workflow artifacts (14-day retention).

---

## 15. Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd DevSecOpsPlatform

# 2. Configure environment
cp .env.example .env
# Generate SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Generate FIELD_ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Set EMAIL_HOST / EMAIL_PORT / DEFAULT_FROM_EMAIL for 2FA OTP delivery
# Paste all values into .env

# 3. Start the stack
docker compose up -d --build

# 4. Create admin user
docker compose exec django python manage.py createsuperuser

# 5. Open http://localhost:8000
# Login → 2FA OTP sent to admin email → enter code → dashboard
```

**Production deployment:** set `DJANGO_SETTINGS_MODULE=config.settings.prod`, configure HTTPS, point `PLATFORM_URL` to your domain for correct OTP email links.

---

## 16. Project Structure

```
DevSecOpsPlatform/
├── apps/
│   ├── accounts/           # Auth, 2FA, RBAC, user management
│   │   └── README.md
│   ├── inventory/          # Device inventory, ICMP/SNMP polling, discovery
│   │   └── README.md
│   ├── provisioning/       # Config templates, SSH push, config pull, audit log
│   │   ├── config_templates/   # 9 built-in .j2 templates
│   │   └── README.md
│   ├── cli/                # WebSocket SSH terminal + REST command API
│   │   └── README.md
│   ├── monitoring/         # Alerts, AlertManager webhook, Grafana
│   │   └── README.md
│   └── security/           # Compliance rules, golden config drift
├── api/
│   └── urls.py             # Central DRF router — all /api/* endpoints
├── config/
│   ├── settings/
│   │   ├── base.py         # Shared settings
│   │   ├── dev.py          # Development overrides
│   │   ├── prod.py         # Production hardening (HTTPS, CSP, HSTS)
│   │   └── test.py         # CI test settings (in-memory SQLite, no Redis)
│   ├── celery.py           # Celery app + autodiscovery
│   └── asgi.py             # ASGI routing (HTTP + WebSocket)
├── templates/              # Django HTML templates (Bootstrap 5 dark theme)
│   ├── base.html           # Sidebar, topbar, flash messages
│   ├── accounts/           # Login, verify-otp, profile, users
│   ├── inventory/          # Dashboard, device list/detail/form
│   ├── provisioning/       # Home, push, audit, file template editor
│   ├── cli/                # xterm.js console
│   ├── monitoring/         # Alert list, dashboards
│   └── emails/             # OTP email (HTML + text)
├── static/
│   ├── css/main.css        # Dark theme CSS variables
│   └── js/topology.js      # Animated SVG network topology map
├── fixtures/
│   ├── devices.json        # 15 EVE-NG devices
│   └── compliance_rules.json   # 12 security rules
├── prometheus/
│   ├── prometheus.yml      # Scrape config (SNMP targets)
│   ├── alertmanager.yml    # Routing + inhibition rules
│   └── rules/alerts.yml    # 8 alert rule definitions
├── grafana/
│   ├── dashboards/         # Provisioned network overview dashboard
│   └── datasources/        # Prometheus datasource config
├── snmp_exporter/
│   └── snmp.yml            # SNMP OID mappings for Cisco IOS
├── .github/workflows/
│   └── devsecops.yml       # CI/CD: lint → SAST → audit → test → Trivy
├── Dockerfile              # python:3.11-slim, non-root appuser
├── docker-compose.yml      # 9-service stack
├── entrypoint.sh           # migrate + collectstatic + loaddata on startup
├── requirements.txt        # All Python dependencies pinned
├── pyproject.toml          # Bandit + coverage config
└── .env.example            # Environment variable template
```
