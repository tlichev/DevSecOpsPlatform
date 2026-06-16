# Monitoring App

Real-time network monitoring for the DevSecOps Platform. Collects metrics from network devices via SNMP, stores alert state in Django, visualises data through an embedded Grafana dashboard, and sends HTML email notifications when thresholds are exceeded.

---

## Architecture

```
Network Devices (SNMP)
        │
        ▼
  snmp-exporter  ◄── scrape
        │
        ▼
   Prometheus  ──── evaluates rules ──► Alertmanager ──► Django webhook
        │                                                       │
        ▼                                                       ▼
     Grafana                                              Celery worker
  (embedded in                                          sends HTML email
   platform UI)
```

---

## Features

### 1. Monitoring Home (`/monitoring/`)

Four live stat cards pulled from the database on every page load:

| Card | Data source |
|------|-------------|
| Active Alerts | `Alert.status == 'firing'` count |
| Critical | firing alerts with `severity == 'critical'` |
| Devices Up | `Device.status == 'up'` count |
| Devices Down | `Device.status == 'down'` count |

Below the stats:

- **Embedded Grafana dashboard** — full-height iframe showing the `netops-overview / cisco-switches` dashboard in kiosk mode (`kiosk=tv&theme=dark&refresh=30s`). Auto-refreshes every 30 seconds. Full-screen link opens Grafana directly.
- **Firing alerts table** — shows the 10 most recent unacknowledged firing alerts (severity, name, instance, site, age). Only rendered when alerts exist.

### 2. Alert List (`/monitoring/alerts/`)

Paginated table (30 per page) of all alerts with:

- **Search** — full-text across `alertname`, `instance`, `summary`
- **Filters** — status (firing / resolved), severity (critical / warning / info), site, acknowledged (yes / no)
- **Acknowledge** — engineers can acknowledge alerts with an optional note; acknowledging hides them from the firing alerts summary

### 3. Dashboards Page (`/monitoring/dashboards/`)

Links to three pre-provisioned Grafana dashboards:

| Dashboard | UID | Description |
|-----------|-----|-------------|
| Network Overview | `netops-overview` | Interface traffic, device status, error rates |
| Interface Traffic | `netops-interfaces` | Per-device bandwidth (ifHCIn/OutOctets) |
| Alert History | `netops-alerts` | AlertManager timeline and firing counts |

---

## Prometheus Alert Rules

Defined in `prometheus/rules/alerts.yml`. Evaluated by Prometheus and forwarded to Alertmanager.

### Device Availability (`interval: 30s`)

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `DeviceDown` | `up{job=~"snmp_.*"} == 0` | critical | 2 min |

### Interface Status (`interval: 30s`)

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `InterfaceDown` | `ifOperStatus{ifName!~"Bl.*\|Nu.*\|Lo.*"} == 2` | warning | 2 min |

Loopback, Null, and Blueprint interfaces are excluded from the filter.

### Interface Utilization (`interval: 60s`)

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `HighInboundUtilization` | inbound > 85% of `ifHighSpeed` | warning | 5 min |
| `HighOutboundUtilization` | outbound > 85% of `ifHighSpeed` | warning | 5 min |

The PromQL formula matches the Grafana dashboard panel exactly:
```
(rate(ifHCInOctets[5m]) * 8) / (ifHighSpeed * 1000000) * 100 > 85
```

### Interface Errors & Discards (`interval: 60s`)

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `HighInterfaceErrors` | in/out errors > 10/s | warning | 5 min |
| `HighInterfaceDiscards` | in/out discards > 5/s | warning | 5 min |

### Platform Health

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `DjangoDown` | `up{job="django"} == 0` | critical | 1 min |
| `HighCPULoad` | CPU idle < 15% (node exporter) | warning | 5 min |

---

## Alert Ingestion Pipeline

### Webhook endpoint

```
POST /api/alerts/webhook/
```

Accepts batched payloads from **Alertmanager** and **Grafana Unified Alerting** (both use the same format). For each alert in the payload:

1. Creates or updates an `Alert` record keyed by `fingerprint` (upsert).
2. If a new firing alert is created → queues `send_alert_email` Celery task.
3. If an existing alert resolves → queues `send_alert_email` with `state='resolved'`.
4. If `alertname == DeviceDown` → immediately updates the matching `Device.status` in the inventory.
5. After the loop → triggers `mark_devices_from_alerts` async task to reconcile all device statuses.

### Grafana contact point

Configure under **Alerting → Contact points**:

- **Integration**: Webhook
- **URL**: `http://django:8000/api/alerts/webhook/`

---

## Email Notifications

Implemented as a Celery task (`monitoring.send_alert_email`) on the `monitoring` queue.

**Features:**
- Branded dark-themed HTML email (`templates/emails/alert_notification.html`)
- Severity-coloured header: red for critical, amber for warning, green for resolved
- Alert details table: device, site, severity, status, summary, description
- "View Alert in Platform" CTA button
- Deduplication: one email per `(alert, state, recipient)` — tracked in `AlertNotification` model
- Auto-retry on SMTP failure: up to 3 retries with 60-second backoff

**Configuration** (`.env`):

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-account@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=NetOps Alerts <your-account@gmail.com>
ALERT_EMAIL_RECIPIENTS=recipient@example.com
PLATFORM_URL=http://<host-ip>:8000
```

> Gmail requires a 16-character **App Password** (Google Account → Security → 2-Step Verification → App passwords). A regular Gmail password will be rejected.

---

## REST API

Base path: `/api/monitoring/`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/monitoring/alerts/` | JWT | List all alerts (filterable, searchable) |
| GET | `/api/monitoring/alerts/{id}/` | JWT | Alert detail |
| POST | `/api/monitoring/alerts/{id}/acknowledge/` | JWT | Acknowledge an alert |
| GET | `/api/monitoring/alerts/active-summary/` | JWT | Count by severity |
| POST | `/api/alerts/webhook/` | None | Alertmanager / Grafana webhook receiver |

Filter parameters for the list endpoint: `status`, `severity`, `site`, `alertname`, `acknowledged`.
Search parameter: `?q=<text>` matches `alertname`, `instance`, `summary`.

---

## Data Models

### `Alert`

| Field | Type | Notes |
|-------|------|-------|
| `fingerprint` | CharField(64) | Unique key from Alertmanager |
| `alertname` | CharField | e.g. `DeviceDown`, `InterfaceDown` |
| `instance` | CharField | Device IP or hostname |
| `site` | CharField | Site label from Prometheus |
| `severity` | CharField | `critical` / `warning` / `info` |
| `status` | CharField | `firing` / `resolved` |
| `summary` | TextField | Short human-readable summary |
| `description` | TextField | Full alert description |
| `raw_labels` | JSONField | All Prometheus labels |
| `raw_payload` | JSONField | Full alert payload |
| `starts_at` | DateTimeField | When the alert first fired |
| `ends_at` | DateTimeField | When it resolved (null if firing) |
| `acknowledged` | BooleanField | Whether an engineer acknowledged it |
| `acknowledged_by` | FK → User | Who acknowledged |
| `ack_note` | TextField | Optional acknowledgement note |

### `AlertNotification`

Tracks every email sent to prevent duplicate delivery.

| Field | Type | Notes |
|-------|------|-------|
| `alert` | FK → Alert | The alert this email belongs to |
| `recipient` | EmailField | Recipient address |
| `alert_state` | CharField | `firing` or `resolved` |
| `sent_at` | DateTimeField | Auto-set on creation |
| `success` | BooleanField | False if SMTP failed |
| `error_msg` | TextField | SMTP error detail on failure |

---

## Background Tasks (Celery)

| Task name | Queue | Trigger | Description |
|-----------|-------|---------|-------------|
| `monitoring.send_alert_email` | monitoring | Webhook on new/resolved alert | Renders and sends HTML email |
| `monitoring.sync_alerts` | monitoring | Scheduled (celery-beat) | Polls Prometheus `/api/v1/alerts` as reconciliation fallback |
| `monitoring.mark_devices_from_alerts` | monitoring | After each webhook call | Syncs `Device.status` based on firing `DeviceDown` alerts |
