# Inventory App (`apps/inventory`)

The Inventory app is the foundation of the platform. It maintains the authoritative database of all network devices and provides automated discovery of devices on the management subnet.

---

## Table of Contents

- [Purpose](#purpose)
- [File Structure](#file-structure)
- [Data Models](#data-models)
- [REST API Reference](#rest-api-reference)
- [Auto-Discovery](#auto-discovery)
- [Celery Tasks](#celery-tasks)
- [Permissions](#permissions)
- [Admin Interface](#admin-interface)
- [UI Pages](#ui-pages)
- [Usage Examples](#usage-examples)

---

## Purpose

- Store every network device: hostname, IP, type, vendor, OS version, status, SSH and SNMP credentials
- Automatically discover live devices on any subnet using ICMP ping + SNMP `sysName` retrieval
- Provide a REST API consumed by all other apps (provisioning, security, monitoring) to look up devices
- Track device reachability and update online/offline status asynchronously

---

## File Structure

```
apps/inventory/
├── models.py          # Device and DiscoveryJob models
├── serializers.py     # DRF serializers (full + lightweight list)
├── views.py           # DeviceViewSet and DiscoveryJobViewSet
├── urls.py            # API router: /api/inventory/
├── ui_urls.py         # Browser URL patterns: /inventory/
├── ui_views.py        # Django template views
├── permissions.py     # ReadOnlyOrAbove, IsAdminOrNetworkEngineer, IsAdminOnly
├── tasks.py           # Celery tasks: discovery, reachability, periodic refresh
├── admin.py           # Django admin registration
├── apps.py            # AppConfig
└── management/
    └── commands/
        └── create_superuser_if_missing.py  # Used by Docker entrypoint
```

---

## Data Models

### `Device`

The core model representing a single network device.

| Field | Type | Description |
|---|---|---|
| `hostname` | CharField(255) | Unique device name |
| `ip_address` | GenericIPAddressField | Unique management IP |
| `device_type` | CharField | `router`, `switch`, `firewall`, `server`, `unknown` |
| `vendor` | CharField | `cisco`, `juniper`, `arista`, `paloalto`, `pfsense`, `other` |
| `os_version` | CharField | IOS version string e.g. `15.9(3)M6` |
| `description` | TextField | Free text |
| `status` | CharField | `online`, `offline`, `unknown`, `maintenance` |
| `ssh_username` | CharField | SSH login username |
| `ssh_password` | CharField | SSH password (write-only in API) |
| `ssh_port` | PositiveIntegerField | Default: 22 |
| `snmp_community` | CharField | SNMP v2c community string |
| `snmp_version` | CharField | `2c` or `3` |
| `site` | CharField | Physical location label |
| `rack` | CharField | Rack identifier |
| `tags` | JSONField | List of string tags |
| `discovered_at` | DateTimeField | When auto-discovery found it |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated on save |
| `created_by` | FK(User) | Who added it |

**Computed property `netmiko_device_type`** — maps vendor+device_type to a Netmiko platform string:

| vendor | device_type | netmiko_device_type |
|---|---|---|
| cisco | router | `cisco_ios` |
| cisco | switch | `cisco_ios` |
| cisco | firewall | `cisco_asa` |
| juniper | router/switch | `juniper_junos` |
| arista | switch | `arista_eos` |

### `DiscoveryJob`

Tracks a single subnet discovery scan initiated by a user.

| Field | Type | Description |
|---|---|---|
| `subnet` | CharField | CIDR notation e.g. `192.168.100.0/24` |
| `status` | CharField | `pending`, `running`, `completed`, `failed` |
| `started_at` | DateTimeField | When Celery task began |
| `completed_at` | DateTimeField | When it finished |
| `devices_found` | PositiveIntegerField | Live hosts discovered |
| `devices_added` | PositiveIntegerField | New devices added to DB |
| `log` | TextField | Per-IP scan log |
| `initiated_by` | FK(User) | Who triggered it |
| `celery_task_id` | CharField | Celery task UUID for tracking |

---

## REST API Reference

Base path: `/api/inventory/`

### Devices

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/inventory/devices/` | List all devices (paginated) | Any authenticated |
| POST | `/api/inventory/devices/` | Create a device | Network Engineer+ |
| GET | `/api/inventory/devices/{id}/` | Get device details | Any authenticated |
| PUT | `/api/inventory/devices/{id}/` | Full update | Network Engineer+ |
| PATCH | `/api/inventory/devices/{id}/` | Partial update | Network Engineer+ |
| DELETE | `/api/inventory/devices/{id}/` | Delete device | Network Engineer+ |
| POST | `/api/inventory/devices/{id}/check_reachability/` | Ping device async | Network Engineer+ |
| GET | `/api/inventory/devices/{id}/status_detail/` | Get live status fields | Any authenticated |

**Query parameters for GET /devices/:**

| Parameter | Example | Description |
|---|---|---|
| `status` | `?status=online` | Filter by status |
| `device_type` | `?device_type=router` | Filter by type |
| `vendor` | `?vendor=cisco` | Filter by vendor |
| `site` | `?site=HQ` | Filter by site |
| `search` | `?search=core` | Search hostname, IP, description, site |
| `ordering` | `?ordering=-created_at` | Sort (prefix `-` for descending) |
| `page` | `?page=2` | Pagination (25 per page) |

**Example response — GET /api/inventory/devices/{id}/:**
```json
{
  "id": 1,
  "hostname": "R1",
  "ip_address": "192.168.100.1",
  "device_type": "router",
  "device_type_display": "Router",
  "vendor": "cisco",
  "os_version": "15.9(3)M6",
  "description": "Edge Router",
  "status": "online",
  "status_display": "Online",
  "ssh_username": "admin",
  "ssh_port": 22,
  "snmp_community": "public",
  "snmp_version": "2c",
  "site": "HQ",
  "rack": "R1",
  "tags": ["edge", "ospf"],
  "discovered_at": "2024-01-01T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "netmiko_device_type": "cisco_ios"
}
```

### Discovery Jobs

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/inventory/discovery/` | List all discovery jobs | Network Engineer+ |
| POST | `/api/inventory/discovery/` | Start new discovery scan | Network Engineer+ |
| GET | `/api/inventory/discovery/{id}/` | Get job details and log | Network Engineer+ |
| GET | `/api/inventory/discovery/{id}/result/` | Get job result summary | Network Engineer+ |

**POST /api/inventory/discovery/ request body:**
```json
{
  "subnet": "192.168.100.0/24"
}
```

**Response:**
```json
{
  "id": 1,
  "subnet": "192.168.100.0/24",
  "status": "pending",
  "started_at": null,
  "completed_at": null,
  "devices_found": 0,
  "devices_added": 0,
  "log": "",
  "initiated_by_username": "admin",
  "celery_task_id": "a1b2c3d4-...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Auto-Discovery

When a discovery job is created, the `run_discovery` Celery task executes on the `discovery` queue:

```
For each host IP in the subnet CIDR:
  1. ICMP ping (subprocess ping -c 1)
     → skip if unreachable
  2. If alive → check if already in Device table
     → skip if exists (updates nothing to avoid overwriting manual data)
  3. SNMP GET sysName (OID 1.3.6.1.2.1.1.5.0)
     → use as hostname if available
  4. DNS reverse lookup as fallback
  5. Use IP-based hostname (192-168-100-1) as last resort
  6. Create Device with status=online
```

The job log captures every decision per IP address, viewable in the API and admin.

**Concurrency note:** The task runs sequentially per IP to avoid overwhelming devices with simultaneous SNMP requests. For large subnets (/16 and larger), break into smaller /24 batches.

---

## Celery Tasks

Defined in `tasks.py`, routed to the `discovery` queue:

### `run_discovery(job_id)`
- Triggered by: POST `/api/inventory/discovery/`
- Updates `DiscoveryJob` status in real time
- Creates `Device` records for newly found hosts

### `check_device_reachability(device_id)`
- Triggered by: POST `/api/inventory/devices/{id}/check_reachability/`
- Pings the device, updates `Device.status` to `online` or `offline`
- Returns: `{"device_id": 1, "status": "online"}`

### `refresh_all_device_status()`
- Triggered by: Celery Beat on a configurable schedule
- Dispatches `check_device_reachability` for every device in the database
- Configure via Django admin → Periodic Tasks (django-celery-beat)

---

## Permissions

Defined in `permissions.py` and used across all apps:

| Class | Rule |
|---|---|
| `ReadOnlyOrAbove` | Any authenticated user can read (GET). Mutations (POST/PUT/PATCH/DELETE) require `network_engineer` or `admin` role. |
| `IsAdminOrNetworkEngineer` | All methods require `network_engineer` or `admin` role. |
| `IsAdminOnly` | All methods require `admin` role or Django superuser. |

Role is stored in `apps.security.models.UserProfile.role` (OneToOne with Django User).
Superusers bypass all role checks.

---

## Admin Interface

Access at `http://localhost:8000/admin/`

**Device admin features:**
- List with filters: status, device_type, vendor
- Search by: hostname, IP, site
- Read-only fields: created_at, updated_at, discovered_at

**DiscoveryJob admin features:**
- Lists scan history with device counts
- Read-only: timestamps, task ID

---

## UI Pages

| URL | Template | Description |
|---|---|---|
| `/inventory/` | `device_list.html` | Paginated device table with status badges |
| `/inventory/{id}/` | `device_detail.html` | Device info + quick action buttons |
| `/inventory/add/` | `device_add.html` | Form to add a device (calls API via JS) |
| `/inventory/discovery/` | `discovery_list.html` | Discovery job history + start new scan |

---

## Usage Examples

### Add a device via API

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"adminpassword123"}' | jq -r .access)

curl -X POST http://localhost:8000/api/inventory/devices/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "Core-SW",
    "ip_address": "192.168.100.10",
    "device_type": "switch",
    "vendor": "cisco",
    "ssh_username": "admin",
    "ssh_password": "cisco123",
    "site": "DataCenter",
    "tags": ["core", "l3", "ospf"]
  }'
```

### Start auto-discovery

```bash
curl -X POST http://localhost:8000/api/inventory/discovery/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subnet": "192.168.100.0/24"}'
```

### Check discovery job status

```bash
curl http://localhost:8000/api/inventory/discovery/1/ \
  -H "Authorization: Bearer $TOKEN"
```

### Filter online routers

```bash
curl "http://localhost:8000/api/inventory/devices/?status=online&device_type=router" \
  -H "Authorization: Bearer $TOKEN"
```

### Trigger reachability check

```bash
curl -X POST http://localhost:8000/api/inventory/devices/1/check_reachability/ \
  -H "Authorization: Bearer $TOKEN"
```
