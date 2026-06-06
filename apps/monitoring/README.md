# Monitoring App (`apps/monitoring`)

The Monitoring app is the observability hub of the platform. It does not collect metrics directly — that is Prometheus's job. Instead it ingests alerts from AlertManager, provides a registry of Grafana dashboards to embed in the UI, and exposes the main platform dashboard.

---

## Table of Contents

- [Purpose](#purpose)
- [File Structure](#file-structure)
- [Data Models](#data-models)
- [AlertManager Webhook](#alertmanager-webhook)
- [Grafana Integration](#grafana-integration)
- [REST API Reference](#rest-api-reference)
- [UI Pages](#ui-pages)
- [Alert Lifecycle](#alert-lifecycle)
- [Usage Examples](#usage-examples)

---

## Purpose

- Receive alert payloads from Prometheus AlertManager via HTTP webhook
- Store alerts in the database with severity, status, device association, and timestamps
- Allow operators to acknowledge alerts from the UI
- Maintain a registry of Grafana dashboard UIDs to embed in the platform UI via `<iframe>`
- Display a real-time summary dashboard combining device counts, alert counts, and a live Grafana embed

---

## File Structure

```
apps/monitoring/
├── models.py           # Alert, GrafanaDashboard models
├── serializers.py      # DRF serializers + AlertManagerWebhookSerializer
├── views.py            # AlertViewSet, GrafanaDashboardViewSet, alertmanager_webhook
├── urls.py             # API router + webhook URL
├── ui_urls.py          # Browser URL patterns: /dashboard/
├── ui_views.py         # Django template views
├── admin.py            # Django admin registration
├── apps.py             # AppConfig
└── fixtures/
    └── initial_dashboards.json   # Seed data for GrafanaDashboard table
```

---

## Data Models

### `Alert`

Represents a single alert instance received from AlertManager. Alerts are identified by `fingerprint` and upserted (update-or-create) so re-fired alerts update the existing record instead of creating duplicates.

| Field | Type | Description |
|---|---|---|
| `alert_name` | CharField(255) | `alertname` label from Prometheus rule |
| `severity` | CharField | `critical`, `warning`, `info`, `resolved` |
| `status` | CharField | `firing` or `resolved` |
| `device` | FK(Device, nullable) | Matched by extracting IP from `instance` label |
| `instance` | CharField | Prometheus instance label (e.g. `192.168.100.1:161`) |
| `labels` | JSONField | Full labels dict from AlertManager |
| `annotations` | JSONField | Full annotations dict (summary, description) |
| `starts_at` | DateTimeField | When the alert began firing |
| `ends_at` | DateTimeField | When it was resolved (null if still firing) |
| `generator_url` | URLField | Link to the Prometheus expression that generated it |
| `fingerprint` | CharField(64) | AlertManager's unique hash, used for upsert — indexed |
| `received_at` | DateTimeField | When Django received it |
| `acknowledged` | BooleanField | Whether an operator has acknowledged it |
| `acknowledged_at` | DateTimeField | When it was acknowledged |

**Database indexes:**
- `(status, severity)` — for fast dashboard queries like "all critical firing alerts"
- `alert_name` — for searching by rule name

### `GrafanaDashboard`

A registry entry that tells the Django UI which Grafana dashboards to embed.

| Field | Type | Description |
|---|---|---|
| `title` | CharField(255) | Human-readable display name |
| `uid` | CharField(64) | Grafana dashboard UID (unique) |
| `panel_id` | IntegerField | Optional: embed a single panel instead of the full dashboard |
| `description` | TextField | What this dashboard shows |
| `embed_url` | CharField | Optional: override the computed iframe URL |
| `order` | PositiveIntegerField | Sort order in the sidebar list |

**Fixtures:** Three dashboards are seeded automatically on first start via `initial_dashboards.json`:
- `network-overview` — bandwidth, CPU, interface status, OSPF
- `node-exporter-full` — host machine metrics
- `alertmanager-alerts` — live alert panel

---

## AlertManager Webhook

### Endpoint

```
POST /api/monitoring/webhook/alertmanager/
```

This endpoint is **public** (`AllowAny` permission) because AlertManager runs as an internal Docker service without user credentials. It is protected by network isolation — only containers on the `monitoring` network can reach it.

### Payload format

AlertManager sends the Prometheus Alerting API v4 format:

```json
{
  "version": "4",
  "groupKey": "{}:{alertname=\"InterfaceDown\"}",
  "status": "firing",
  "receiver": "django_webhook",
  "groupLabels": {"alertname": "InterfaceDown"},
  "commonLabels": {"alertname": "InterfaceDown", "severity": "critical"},
  "commonAnnotations": {"summary": "Interface down on 192.168.100.1"},
  "externalURL": "http://alertmanager:9093",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "InterfaceDown",
        "instance": "192.168.100.1:161",
        "severity": "critical",
        "ifDescr": "GigabitEthernet0/0"
      },
      "annotations": {
        "summary": "Interface GigabitEthernet0/0 down on 192.168.100.1",
        "description": "Interface has been down for more than 2 minutes."
      },
      "startsAt": "2024-06-01T12:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph?...",
      "fingerprint": "a1b2c3d4e5f6"
    }
  ]
}
```

### Processing logic

For each alert in the `alerts` array:

1. Extract `alertname`, `severity`, `status`, `instance`, `fingerprint` from labels
2. Parse `instance` label (`ip:port` format) → extract IP → look up `Device` by IP address
3. Parse ISO 8601 timestamps for `startsAt` / `endsAt`
4. `Alert.objects.update_or_create(fingerprint=fingerprint, defaults={...})`
   - If the alert already exists (same fingerprint): **update** all fields
   - If new: **create** a new record
5. Log each alert with its device association

### Response

```json
{
  "received": 3,
  "created": 1
}
```

`received` = total alerts in payload, `created` = newly inserted (vs updated).

---

## Grafana Integration

### Iframe embedding

The Django templates embed Grafana dashboards using `<iframe>` with the `kiosk=tv` parameter to hide the Grafana navigation bar:

```html
<iframe
  src="{{ grafana_url }}/d/{{ dashboard.uid }}?orgId=1&refresh=30s&kiosk=tv"
  title="{{ dashboard.title }}">
</iframe>
```

**Critical settings** that make embedding work:

In `docker-compose.yml`:
```yaml
GF_SECURITY_ALLOW_EMBEDDING: "true"
GF_AUTH_ANONYMOUS_ENABLED: "true"
GF_AUTH_ANONYMOUS_ORG_ROLE: Viewer
```

In `devsecops_platform/settings.py`:
```python
X_FRAME_OPTIONS = "SAMEORIGIN"
```

In `.env`:
```
GRAFANA_URL=http://localhost:3000   # browser-facing URL
GRAFANA_INTERNAL_URL=http://grafana:3000   # server-side API calls
```

### Dashboard provisioning

Grafana auto-loads the `network_overview.json` dashboard from `grafana/dashboards/` via the provisioning configuration in `grafana/provisioning/dashboards/dashboards.yml`. No manual dashboard import is needed.

---

## REST API Reference

Base path: `/api/monitoring/`

### Alerts

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/monitoring/alerts/` | List all alerts (paginated) | Any authenticated |
| GET | `/api/monitoring/alerts/{id}/` | Get alert detail | Any authenticated |
| PATCH | `/api/monitoring/alerts/{id}/acknowledge/` | Mark alert as acknowledged | Network Engineer+ |
| POST | `/api/monitoring/webhook/alertmanager/` | AlertManager webhook receiver | Public (internal only) |

**Query parameters for GET /alerts/:**

| Parameter | Example | Description |
|---|---|---|
| `severity` | `?severity=critical` | Filter by severity |
| `status` | `?status=firing` | Filter by status |
| `acknowledged` | `?acknowledged=false` | Filter unacknowledged |
| `search` | `?search=Interface` | Search alert_name, instance |

**Alert response:**
```json
{
  "id": 5,
  "alert_name": "InterfaceDown",
  "severity": "critical",
  "status": "firing",
  "device_hostname": "Core-SW",
  "instance": "192.168.100.10:161",
  "labels": {"alertname": "InterfaceDown", "ifDescr": "GigabitEthernet0/1"},
  "annotations": {"summary": "Interface GigabitEthernet0/1 down"},
  "starts_at": "2024-06-01T12:00:00Z",
  "ends_at": null,
  "fingerprint": "a1b2c3d4",
  "received_at": "2024-06-01T12:00:05Z",
  "acknowledged": false,
  "acknowledged_at": null
}
```

### Grafana Dashboards

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/monitoring/dashboards/` | List all registered dashboards | Any authenticated |
| GET | `/api/monitoring/dashboards/{id}/` | Get dashboard detail | Any authenticated |

---

## UI Pages

| URL | Template | Description |
|---|---|---|
| `/dashboard/` | `monitoring/dashboard.html` | Main dashboard: stats cards + Grafana iframe + recent alerts |
| `/dashboard/alerts/` | `monitoring/alerts.html` | Full alert table with acknowledge button |
| `/dashboard/grafana/` | `monitoring/grafana_embed.html` | Dashboard selector + full-size iframe |

### Dashboard stats cards

| Card | Query |
|---|---|
| Total Devices | `Device.objects.count()` |
| Online | `Device.objects.filter(status="online").count()` |
| Offline | `Device.objects.filter(status="offline").count()` |
| Active Alerts | `Alert.objects.filter(status="firing").count()` |

---

## Alert Lifecycle

```
Prometheus evaluates rule (every 30s)
         │
         ▼ (alert condition true for `for:` duration)
Prometheus fires alert → sends to AlertManager
         │
         ▼
AlertManager groups + deduplicates (group_wait: 30s)
         │
         ▼
AlertManager POST /api/monitoring/webhook/alertmanager/
         │
         ▼
Django upserts Alert record
  status="firing", severity from labels, device matched by IP
         │
         ▼
Alert visible in:
  - /dashboard/ (recent alerts table)
  - /dashboard/alerts/ (full alert table)
  - /api/monitoring/alerts/ (REST API)
         │
         ▼ (condition resolves)
AlertManager sends resolved payload (same fingerprint)
         │
         ▼
Django updates Alert: status="resolved", ends_at=<timestamp>
```

---

## Usage Examples

### Get all critical firing alerts

```bash
curl "http://localhost:8000/api/monitoring/alerts/?severity=critical&status=firing" \
  -H "Authorization: Bearer $TOKEN"
```

### Acknowledge an alert

```bash
curl -X PATCH http://localhost:8000/api/monitoring/alerts/5/acknowledge/ \
  -H "Authorization: Bearer $TOKEN"
```

### Manually test the webhook (simulate AlertManager)

```bash
curl -X POST http://localhost:8000/api/monitoring/webhook/alertmanager/ \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "firing",
    "receiver": "django_webhook",
    "groupLabels": {"alertname": "TestAlert"},
    "commonLabels": {},
    "commonAnnotations": {},
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "warning",
        "instance": "192.168.100.1:161"
      },
      "annotations": {"summary": "Test alert from curl"},
      "startsAt": "2024-06-01T00:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "fingerprint": "test-fingerprint-001"
    }]
  }'
```

### Register a new Grafana dashboard

```bash
curl -X POST http://localhost:8000/api/monitoring/dashboards/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "OSPF Topology",
    "uid": "ospf-topology",
    "description": "OSPF neighbor state and LSA counts",
    "order": 4
  }'
```
