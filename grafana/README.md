# Grafana (`grafana/`)

Grafana provides the visualization layer. It is automatically provisioned with a Prometheus datasource and a Network Overview dashboard on first startup. Dashboards are embedded in the Django UI via `<iframe>`.

---

## File Structure

```
grafana/
├── dashboards/
│   └── network_overview.json           # Network Overview dashboard (auto-loaded)
└── provisioning/
    ├── datasources/
    │   └── prometheus.yml              # Auto-configures Prometheus datasource
    └── dashboards/
        └── dashboards.yml              # Tells Grafana where to find dashboard JSON files
```

---

## Provisioning System

Grafana's provisioning system reads YAML configuration from `/etc/grafana/provisioning/` on startup and applies it automatically. No manual clicks needed.

### Datasource provisioning — `provisioning/datasources/prometheus.yml`

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 30s
      httpMethod: POST
```

`access: proxy` means Grafana fetches data from Prometheus server-side. The browser never contacts Prometheus directly.

`isDefault: true` means all new panels default to this datasource.

### Dashboard provisioning — `provisioning/dashboards/dashboards.yml`

```yaml
providers:
  - name: DevSecOps Platform
    type: file
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

Every JSON file in `/var/lib/grafana/dashboards` (mapped to `grafana/dashboards/` on the host) is loaded as a dashboard. Grafana polls for changes every 30 seconds.

---

## Dashboards

### `network_overview.json` — Network Overview

**UID:** `network-overview`
**Tags:** `network`, `cisco`, `snmp`
**Refresh:** 30 seconds

| Panel | Type | PromQL |
|---|---|---|
| CPU Utilization per Device | Stat | `cpmCPUTotal5minRev{job="snmp_cisco"}` |
| Interface Bandwidth In | Time series | `rate(ifInOctets{job="snmp_cisco"}[5m])` |
| Interface Bandwidth Out | Time series | `rate(ifOutOctets{job="snmp_cisco"}[5m])` |
| Interface Status | Stat | `ifOperStatus{job="snmp_cisco"}` |
| OSPF Neighbor State | Stat | `ospfNbrState{job="snmp_cisco"}` |

**Thresholds:**
- CPU: green < 50%, yellow 50–80%, red > 80%
- Interface Status: green = 1 (up), red = 2 (down)
- OSPF Neighbor: green = 8 (Full), red = anything else

---

## Django Integration

### Embedding dashboards

The Django template `grafana_embed.html` embeds dashboards using:

```html
<iframe
  src="http://localhost:3000/d/network-overview?orgId=1&refresh=30s&kiosk=tv"
  title="Network Overview">
</iframe>
```

**URL parameters:**
| Parameter | Value | Effect |
|---|---|---|
| `orgId` | `1` | Default Grafana organization |
| `refresh` | `30s` | Auto-refresh interval |
| `kiosk=tv` | — | Hides Grafana header/sidebar (full panel view) |
| `from` | `now-1h` | Time range start |
| `to` | `now` | Time range end |
| `var-instance` | `192.168.100.1` | Filter by device (if template variable defined) |

### Embedding a single panel

To embed one specific panel instead of the full dashboard:

```
http://localhost:3000/d-solo/network-overview/network-overview?panelId=1&orgId=1&kiosk
```

Set `panel_id` in the `GrafanaDashboard` database record to enable single-panel embeds.

### Anonymous access

Anonymous access is enabled in `docker-compose.yml` so the browser can load the iframe without authentication:

```yaml
GF_AUTH_ANONYMOUS_ENABLED: "true"
GF_AUTH_ANONYMOUS_ORG_ROLE: Viewer
```

Anonymous users are `Viewer` — they can see dashboards but cannot edit them.

---

## Adding a New Dashboard

### Method 1 — Create in UI, then export

1. Open Grafana at `http://localhost:3000`
2. Create a new dashboard with panels
3. Go to Dashboard Settings → JSON Model → Copy JSON
4. Save to `grafana/dashboards/your_dashboard.json`
5. Add to Django's `GrafanaDashboard` table:
   ```bash
   docker compose exec django python manage.py shell -c "
   from apps.monitoring.models import GrafanaDashboard
   GrafanaDashboard.objects.create(title='My Dashboard', uid='my-dashboard', order=5)
   "
   ```

### Method 2 — Write JSON directly

Use the `network_overview.json` as a template. Key fields:

```json
{
  "uid": "my-unique-uid",        // Must be unique across all dashboards
  "title": "My Dashboard",
  "tags": ["custom"],
  "refresh": "30s",
  "panels": [...]
}
```

Save to `grafana/dashboards/` — Grafana loads it within 30 seconds.

---

## Grafana Configuration Reference

All Grafana settings are passed as environment variables in `docker-compose.yml`:

| Variable | Value | Description |
|---|---|---|
| `GF_SECURITY_ADMIN_USER` | `admin` | Admin username |
| `GF_SECURITY_ADMIN_PASSWORD` | `grafanapassword123` | Admin password |
| `GF_SECURITY_ALLOW_EMBEDDING` | `true` | Required for Django iframe embeds |
| `GF_AUTH_ANONYMOUS_ENABLED` | `true` | Allow viewing without login |
| `GF_AUTH_ANONYMOUS_ORG_ROLE` | `Viewer` | Anonymous user role |
| `GF_USERS_ALLOW_SIGN_UP` | `false` | Disable self-registration |
| `GF_SERVER_ROOT_URL` | `http://localhost:3000` | Public URL for links in alerts |
| `GF_SMTP_ENABLED` | `false` | Email alerting disabled |

---

## Grafana API

Grafana exposes a REST API for automation. Use `GRAFANA_INTERNAL_URL` from settings for server-side calls.

```bash
# List all dashboards
curl http://admin:grafanapassword123@localhost:3000/api/search

# Get dashboard by UID
curl http://admin:grafanapassword123@localhost:3000/api/dashboards/uid/network-overview

# Create API key (for programmatic access)
curl -X POST http://admin:grafanapassword123@localhost:3000/api/auth/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "django-key", "role": "Viewer"}'
```

Store the returned key in `GRAFANA_API_KEY` in `.env` for Django to use in future API integrations.

---

## Persistent Storage

Grafana stores its database (users, alert rules created in UI, manually added dashboards) in the `grafana_data` Docker volume. Dashboards defined in the provisioning JSON files are **always** loaded from disk and take precedence over UI edits.

To reset Grafana to a clean state (losing all UI-created content):

```bash
docker compose down
docker volume rm devsecopsplatform_grafana_data
docker compose up -d grafana
```
