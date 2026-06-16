# Inventory App

Core device registry for the NetOps Platform. Manages the full lifecycle of network devices across three physical sites — Sofia, Burgas, and Plovdiv — including SSH credential encryption, ICMP/SNMP polling, network discovery, and a REST API consumed by the dashboard and topology views.

---

## Model — `Device`

Defined in [models.py](models.py).

### Choice fields

**Sites**

| Value     | Label    |
|-----------|----------|
| `sofia`   | Sofia    |
| `burgas`  | Burgas   |
| `plovdiv` | Plovdiv  |
| `wan`     | WAN      |

**Device types**

| Value                | Label               |
|----------------------|---------------------|
| `router`             | Router              |
| `firewall_primary`   | Firewall (Primary)  |
| `firewall_secondary` | Firewall (Secondary)|
| `l2_switch`          | L2 Switch           |
| `wan_switch`         | WAN Switch          |

**Status**

| Value     | Meaning                          |
|-----------|----------------------------------|
| `up`      | Device responded to last poll    |
| `down`    | Device did not respond           |
| `unknown` | Never polled, or polling skipped |

### Fields

| Field            | Type         | Notes                                         |
|------------------|--------------|-----------------------------------------------|
| `hostname`       | CharField    | Unique; primary identifier                    |
| `ip_address`     | GenericIPAddressField | Unique; used for polling and SSH      |
| `wan_ip`         | GenericIPAddressField | Optional; WAN-facing address          |
| `loopback_ip`    | GenericIPAddressField | Optional; loopback/management address |
| `site`           | CharField    | Choices above                                 |
| `device_type`    | CharField    | Choices above                                 |
| `vendor`         | CharField    | e.g. `Cisco`, `Juniper`                       |
| `model`          | CharField    | Hardware model string                         |
| `os_version`     | CharField    | IOS / JunOS version string                    |
| `description`    | TextField    | Free-text notes                               |
| `status`         | CharField    | Updated by polling tasks                      |
| `last_seen`      | DateTimeField | Last time device responded                   |
| `last_polled`    | DateTimeField | Last time polling was attempted               |
| `snmp_community` | CharField    | SNMP read community string                    |
| `snmp_version`   | CharField    | `2c` or `3`                                   |
| `ssh_username`   | CharField    | SSH login username                            |
| `ssh_password`   | TextField    | Fernet-encrypted; never stored in plaintext   |
| `created_at`     | DateTimeField | Auto-set on creation                         |
| `updated_at`     | DateTimeField | Auto-updated on save                         |

**DB indexes:** composite indexes on `(site, status)` and `(site, device_type)` for fast per-site filtering.

### Properties and methods

| Member                      | Description                                              |
|-----------------------------|----------------------------------------------------------|
| `site_color`                | Bootstrap colour name for the site badge                 |
| `device_type_icon`          | Bootstrap Icons class for the device type icon           |
| `role_short`                | Short role label (e.g. `RTR`, `FW1`, `SW`)               |
| `get_plaintext_password()`  | Decrypts `ssh_password` via Fernet                       |
| `set_encrypted_password(p)` | Encrypts and stores plaintext `p` into `ssh_password`    |
| `get_netmiko_params()`      | Returns dict ready for a Netmiko `ConnectHandler` call   |
| `mark_seen()`               | Sets `status=up`, updates `last_seen` and `last_polled`  |
| `mark_down()`               | Sets `status=down`, updates `last_polled`                |

---

## SSH Credential Encryption

Implemented in [utils.py](utils.py) using the `cryptography` library's Fernet symmetric encryption.

```
settings.FIELD_ENCRYPTION_KEY  →  used directly if set
        (absent)               →  SHA-256(SECRET_KEY) → 32-byte key → Fernet
```

**Functions**

- `encrypt_password(plaintext)` → base64 Fernet token (always starts with `gAAAAA`)
- `decrypt_password(ciphertext)` → plaintext; falls back to returning the value as-is if decryption fails (safe for plain-text fixture imports)

The Django Admin's `save_model` and `DeviceForm.save()` both call `set_encrypted_password()` automatically. The serializer exposes `ssh_password` as write-only and handles encryption in `create()` / `update()`.

---

## Views and URLs

All views require login. Write operations additionally require `@engineer_required`.

URLs are mounted at the project root with `app_name = 'inventory'`.

| URL                           | View               | Auth           | Description                                 |
|-------------------------------|--------------------|----------------|---------------------------------------------|
| `/`                           | `dashboard`        | Login          | Main dashboard (renders `dashboard.html`)   |
| `/inventory/`                 | `device_list`      | Login          | Filterable device table                     |
| `/inventory/add/`             | `device_create`    | Engineer+      | Add a new device                            |
| `/inventory/<pk>/`            | `device_detail`    | Login          | Device detail with last 10 audit log events |
| `/inventory/<pk>/edit/`       | `device_edit`      | Engineer+      | Edit existing device                        |
| `/inventory/<pk>/delete/`     | `device_delete`    | Engineer+      | POST-only delete                            |
| `/inventory/<pk>/cli/`        | `cli_views.console`| Engineer+      | Live CLI console (from `apps.cli`)          |
| `/sites/sofia/`               | `site_sofia`       | Login          | Devices filtered to Sofia site              |
| `/sites/burgas/`              | `site_burgas`      | Login          | Devices filtered to Burgas site             |
| `/sites/plovdiv/`             | `site_plovdiv`     | Login          | Devices filtered to Plovdiv site            |

### Device list filtering

`device_list` accepts GET parameters: `site`, `device_type`, `status`, and `q` (search across hostname, IP address, description, and model). Filter state is preserved in the template for sticky dropdowns.

---

## REST API

Defined in [api.py](api.py), registered as `/api/inventory/devices/` via the project router.

**ViewSet:** `DeviceViewSet` (DRF `ModelViewSet`)

**Permission:** `IsEngineerOrReadOnly` — engineers and admins can write; read-only users get GET only.

**Filtering:** `DeviceFilter` (django-filters) on `site`, `device_type`, `status`, `vendor`, `hostname`, `ip_address`. Full-text search on `hostname`, `ip_address`, `description`, `model`. Ordering on any field.

### Standard endpoints

| Method | URL                            | Description              |
|--------|--------------------------------|--------------------------|
| GET    | `/api/inventory/devices/`      | Paginated device list    |
| POST   | `/api/inventory/devices/`      | Create device            |
| GET    | `/api/inventory/devices/<id>/` | Device detail            |
| PUT    | `/api/inventory/devices/<id>/` | Full update              |
| PATCH  | `/api/inventory/devices/<id>/` | Partial update           |
| DELETE | `/api/inventory/devices/<id>/` | Delete device            |

### Custom actions

| Method | URL                                        | Description                                              |
|--------|--------------------------------------------|----------------------------------------------------------|
| POST   | `/api/inventory/devices/<id>/poll/`        | Trigger `poll_device` task for one device                |
| POST   | `/api/inventory/devices/poll_all/`         | Trigger `poll_all_devices` task for all devices          |
| POST   | `/api/inventory/devices/discover/`         | Trigger `discover_network` task                          |
| GET    | `/api/inventory/devices/status_list/`      | Minimal status payload for topology.js                   |
| GET    | `/api/inventory/devices/by_site/?site=X`   | Filter devices by site, returns lightweight list         |

### `dashboard_stats` endpoint

`GET /api/inventory/dashboard-stats/` (authenticated)

Returns a JSON object used to populate dashboard counters:

```json
{
  "total": 12,
  "up": 9,
  "down": 2,
  "unknown": 1,
  "sites_online": 3,
  "active_alerts": 4,
  "critical_alerts": 1,
  "compliance_pct": 87
}
```

Gracefully returns `0` for `active_alerts`, `critical_alerts`, and `compliance_pct` if the `monitoring` or `security` apps are not installed.

### Serializers

| Serializer              | Used by                        | Notes                                               |
|-------------------------|--------------------------------|-----------------------------------------------------|
| `DeviceListSerializer`  | List endpoint, `by_site`       | No credentials, no WAN/loopback IPs                 |
| `DeviceSerializer`      | Detail, create, update         | `ssh_password` is write-only; stored encrypted      |
| `DeviceStatusSerializer`| `status_list`                  | Minimal fields for topology.js (`id`, `hostname`, `site`, `device_type`, `role_short`, `status`) |

---

## Celery Tasks

Defined in [tasks.py](tasks.py).

### `poll_device(device_id)`

Queue: `monitoring` | Retries: 2

1. Loads the device by PK.
2. Runs an ICMP ping (`ping -c 1 -W 2 <ip>`).
3. On success: calls `device.mark_seen()`.
4. On failure: calls `device.mark_down()`.

### `poll_all_devices()`

Queue: `monitoring`

Dispatches a Celery `group` of `poll_device` tasks — one per device in the database. Runs in parallel.

### `discover_network()`

Queue: `discovery`

1. Reads `settings.MGMT_NETWORK` (default `192.168.100.0/24`).
2. Pings every host in the subnet in parallel.
3. For each responding host not already in the database: attempts SNMP `sysName.0` GET to derive a hostname; creates a new `Device` record with `status=unknown`.

### Internal helpers

- `_ping(ip)` — returns `True` if the host responds to a single ICMP probe
- `_snmp_get_sysname(ip, community)` — returns `sysName.0` string or `None`

---

## Forms and Filters

### `DeviceForm` ([forms.py](forms.py))

`ModelForm` for `Device`. Excludes `ssh_password` from the Meta fields and replaces it with a plaintext `ssh_password_plain` `PasswordInput` field. On `save()`, calls `device.set_encrypted_password()` if a value was entered. All widgets have Bootstrap `form-control` / `form-select` classes.

### `DeviceFilter` ([filters.py](filters.py))

`django-filters` FilterSet used by `DeviceViewSet`. Supports:

- Exact match on `site`, `device_type`, `status`
- Case-insensitive contains on `vendor`, `hostname`, `ip_address`

---

## Templates

| Template                            | Description                                                          |
|-------------------------------------|----------------------------------------------------------------------|
| `templates/inventory/device_list.html`   | Stats cards, filter bar, device table with inline poll/delete actions |
| `templates/inventory/device_detail.html` | Two-column detail view with device info, recent audit log, quick actions |
| `templates/inventory/device_form.html`   | Shared Add/Edit form; breadcrumb adapts; SSH password show/hide toggle |

### JavaScript in templates

- **device_list:** `fetch()` calls to `poll/`, `poll_all/`, `discover/` REST endpoints; toast notifications; delete confirmation modal
- **device_detail:** `pollDevice()` with 4-second auto-reload after polling; delete modal wiring
- **device_form:** password field show/hide toggle

---

## Django Admin

`DeviceAdmin` in [admin.py](admin.py) provides:

- Coloured badge display for site, device type, and status in the list view
- Fieldsets grouping fields into: Identity, Classification, Status, SNMP, SSH Credentials, Timestamps
- `save_model` detects whether the password field already contains a Fernet token (prefix `gAAAAA`) before re-encrypting, preventing double-encryption on edit

---

## Configuration

| Setting                  | Used by              | Description                                          |
|--------------------------|----------------------|------------------------------------------------------|
| `FIELD_ENCRYPTION_KEY`   | `utils.py`           | Explicit Fernet key; derived from `SECRET_KEY` if absent |
| `MGMT_NETWORK`           | `discover_network`   | CIDR subnet to scan (default `192.168.100.0/24`)     |

---

## Migrations

| Migration          | Description                                      |
|--------------------|--------------------------------------------------|
| `0001_initial.py`  | Creates `Device` table with all fields and indexes |
