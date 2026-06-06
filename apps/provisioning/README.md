# Provisioning App (`apps/provisioning`)

The Provisioning app handles all configuration delivery to network devices. It renders Jinja2 templates, pushes the resulting commands over SSH via Netmiko (asynchronously through Celery), and records every action in an immutable audit log.

---

## Table of Contents

- [Purpose](#purpose)
- [File Structure](#file-structure)
- [Data Models](#data-models)
- [Jinja2 Template System](#jinja2-template-system)
- [Built-in Configuration Templates](#built-in-configuration-templates)
- [Netmiko SSH Client](#netmiko-ssh-client)
- [Celery Task Flow](#celery-task-flow)
- [REST API Reference](#rest-api-reference)
- [Audit Log](#audit-log)
- [UI Pages](#ui-pages)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)

---

## Purpose

- Store named, versioned Jinja2 configuration templates for any vendor/device type
- Render templates with user-supplied variables at job creation time
- Push rendered configurations to one or many devices simultaneously via SSH
- Track every push: who, what, when, which device, success or failure, duration
- Provide a preview endpoint to test templates without touching devices

---

## File Structure

```
apps/provisioning/
├── models.py               # ConfigTemplate, ProvisioningJob, ProvisioningResult, AuditLog
├── serializers.py          # DRF serializers for all models
├── views.py                # ViewSets: templates, jobs, audit log
├── urls.py                 # API router: /api/provisioning/
├── ui_urls.py              # Browser URL patterns: /provisioning/
├── ui_views.py             # Django template views
├── tasks.py                # Celery task: execute_provisioning_job
├── netmiko_client.py       # SSH connection wrapper around Netmiko
├── jinja_renderer.py       # Jinja2 rendering with StrictUndefined
├── admin.py                # Django admin registration
├── apps.py                 # AppConfig
└── config_templates/       # Built-in Jinja2 template files
    ├── vlan.j2             # VLAN + SVI configuration
    ├── interface.j2        # Interface mode (access/trunk/routed)
    ├── acl.j2              # Extended ACL definition and application
    ├── ospf.j2             # OSPF process and network statements
    └── hardening.j2        # Full security hardening baseline
```

---

## Data Models

### `ConfigTemplate`

Stores a named Jinja2 template body.

| Field | Type | Description |
|---|---|---|
| `name` | CharField(255) | Unique template name |
| `template_type` | CharField | `vlan`, `interface`, `acl`, `routing`, `hardening`, `custom` |
| `description` | TextField | Human-readable description |
| `body` | TextField | Jinja2 template source |
| `variables_schema` | JSONField | JSON Schema describing accepted variables |
| `vendor` | CharField | Leave blank for vendor-agnostic templates |
| `created_by` | FK(User) | Who created it |
| `created_at` / `updated_at` | DateTimeField | Timestamps |

### `ProvisioningJob`

Represents a single push operation targeting one or more devices.

| Field | Type | Description |
|---|---|---|
| `template` | FK(ConfigTemplate) | Which template was used |
| `devices` | M2M(Device) | Target devices |
| `variables` | JSONField | Template render variables |
| `rendered_config` | TextField | Final rendered Cisco config commands |
| `status` | CharField | `pending`, `running`, `success`, `partial`, `failed` |
| `initiated_by` | FK(User) | Who triggered the job |
| `celery_task_id` | CharField | Track Celery execution |
| `started_at` / `completed_at` | DateTimeField | Execution window |

**Status values:**
- `success` — all devices succeeded
- `partial` — at least one device succeeded, at least one failed
- `failed` — zero devices succeeded
- `running` — Celery task is executing

### `ProvisioningResult`

One row per device per job. Contains the raw SSH output and any error message.

| Field | Type | Description |
|---|---|---|
| `job` | FK(ProvisioningJob) | Parent job |
| `device` | FK(Device) | Target device |
| `success` | BooleanField | Whether the push succeeded |
| `output` | TextField | Raw terminal output from device |
| `error` | TextField | Error message if failed |
| `duration_seconds` | FloatField | SSH session duration |
| `executed_at` | DateTimeField | When this result was recorded |

### `AuditLog`

Immutable append-only log. Never deleted, never updated.

| Field | Type | Description |
|---|---|---|
| `action` | CharField | `push_config`, `compliance_check`, `drift_check`, `snapshot`, `discovery` |
| `actor` | FK(User) | Who performed the action |
| `device` | FK(Device) | Target device (nullable) |
| `detail` | JSONField | Structured details (job ID, template name, duration, error) |
| `success` | BooleanField | Outcome |
| `ip_address` | GenericIPAddressField | Source IP (for future API key support) |
| `timestamp` | DateTimeField | Auto-set, indexed |

---

## Jinja2 Template System

Template rendering is handled by `jinja_renderer.py`.

### Key design decisions

- **`StrictUndefined`** — any variable referenced in the template that is not supplied in `variables` raises a `ValueError` immediately. This prevents partial configurations from being pushed to devices.
- **`autoescape=False`** — templates generate Cisco IOS commands, not HTML.
- **`trim_blocks=True` + `lstrip_blocks=True`** — removes extra blank lines caused by Jinja2 control statements.

### Template syntax reference

```jinja2
{# Comments #}
{{ variable }}                          {# Output a variable #}
{{ variable | default("fallback") }}    {# Default value #}
{% for item in list %}...{% endfor %}   {# Loop #}
{% if condition %}...{% endif %}        {# Conditional #}
{{ variable | join(",") }}              {# Join list to string #}
{{ variable ~ " suffix" }}             {# String concatenation #}
```

### Preview endpoint

Test a template with variables **without touching any device**:

```
POST /api/provisioning/templates/{id}/preview/
Body: {"variables": {"vlans": [{"id": 10, "name": "USERS"}]}}
Response: {"rendered": "vlan 10\n name USERS\n"}
```

If a variable is missing, the response is `400 Bad Request` with the error message.

---

## Built-in Configuration Templates

These Jinja2 files in `config_templates/` serve as references. Load them into the database via the admin or API.

### `vlan.j2` — VLAN + SVI Configuration

**Variables:**
```json
{
  "vlans": [
    {
      "id": 10,
      "name": "USERS",
      "ip_address": "10.0.10.1",
      "netmask": "255.255.255.0",
      "description": "User VLAN",
      "helper_address": "10.0.0.10"
    }
  ]
}
```

**Output:**
```
vlan 10
 name USERS
interface Vlan10
 description User VLAN
 ip address 10.0.10.1 255.255.255.0
 ip helper-address 10.0.0.10
 no shutdown
```

### `interface.j2` — Interface Configuration

**Variables:**
```json
{
  "interfaces": [
    {"name": "GigabitEthernet0/1", "mode": "access", "vlan": 10, "description": "PC1"},
    {"name": "GigabitEthernet0/2", "mode": "trunk", "trunk_vlans": [10, 20, 99]},
    {"name": "GigabitEthernet0/0", "mode": "routed", "ip_address": "10.0.0.1", "netmask": "255.255.255.0"}
  ]
}
```

### `acl.j2` — Extended Access Control List

**Variables:**
```json
{
  "acls": [
    {
      "name": "BLOCK_TELNET",
      "rules": [
        {"action": "deny", "protocol": "tcp", "source": "any", "destination": "any", "port": 23},
        {"action": "permit", "protocol": "ip", "source": "any", "destination": "any"}
      ],
      "apply_to": {"interface": "GigabitEthernet0/0", "direction": "in"}
    }
  ]
}
```

### `ospf.j2` — OSPF Routing

**Variables:**
```json
{
  "process_id": 1,
  "router_id": "1.1.1.1",
  "networks": [
    {"ip": "10.0.10.0", "wildcard": "0.0.0.255", "area": 0},
    {"ip": "192.168.100.0", "wildcard": "0.0.0.255", "area": 0}
  ],
  "passive_interfaces": ["GigabitEthernet0/2"]
}
```

### `hardening.j2` — Security Hardening Baseline

Full security hardening. Variables:
```json
{
  "snmp_v3_user": {
    "group": "MGMT_GROUP",
    "username": "snmpv3user",
    "auth_password": "authpass123",
    "priv_password": "privpass123"
  },
  "snmp_location": "DataCenter-Rack1",
  "snmp_contact": "noc@company.local",
  "mgmt_subnets": ["192.168.100.0 0.0.0.255"],
  "ntp_server": "192.168.100.254"
}
```

Applies: SSH v2, Telnet disabled, password encryption, management ACL, SNMP v3, NTP, banner, logging.

---

## Netmiko SSH Client

`netmiko_client.py` wraps `ConnectHandler` in a context manager pattern.

### Connection parameters

```python
{
    "device_type": device.netmiko_device_type,   # e.g. "cisco_ios"
    "host": device.ip_address,
    "username": device.ssh_username,
    "password": device.ssh_password,
    "port": device.ssh_port,
    "timeout": 30,
    "banner_timeout": 15,
    "conn_timeout": 15,
}
```

### Methods

| Method | Description |
|---|---|
| `push_config(config_lines)` | `send_config_set()` then `save_config()` (writes to NVRAM) |
| `send_command(command)` | Sends a single exec-mode command |
| `get_running_config()` | Returns `show running-config` output |
| `get_version()` | Returns `show version` output |

### Error types

| Exception | Cause |
|---|---|
| `NetmikoError` | Wraps all Netmiko exceptions with a human-readable message |
| `NetMikoTimeoutException` | Device did not respond within timeout |
| `NetMikoAuthenticationException` | Wrong username or password |

---

## Celery Task Flow

```
POST /api/provisioning/jobs/
         │
         ▼
  ProvisioningJob created (status=pending)
         │
         ▼
  execute_provisioning_job.delay(job_id)
         │
         ▼
  Task runs on "provisioning" queue
         │
         ├── Render Jinja2 template → job.rendered_config
         │
         ├── For each device (sequential):
         │     ├── NetmikoClient.push_config(config_lines)
         │     ├── ProvisioningResult.create(success, output, error, duration)
         │     └── AuditLog.create(action="push_config", ...)
         │
         └── Update job.status = success | partial | failed
```

**Why sequential per device?** Netmiko sessions are blocking I/O. Running them sequentially within a single Celery task is safe and predictable. For large device groups (>10), consider splitting into multiple smaller jobs.

---

## REST API Reference

Base path: `/api/provisioning/`

### Templates

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/provisioning/templates/` | List all templates | Network Engineer+ |
| POST | `/api/provisioning/templates/` | Create a template | Network Engineer+ |
| GET | `/api/provisioning/templates/{id}/` | Get template detail | Network Engineer+ |
| PUT/PATCH | `/api/provisioning/templates/{id}/` | Update template | Network Engineer+ |
| DELETE | `/api/provisioning/templates/{id}/` | Delete template | Network Engineer+ |
| POST | `/api/provisioning/templates/{id}/preview/` | Render preview without pushing | Network Engineer+ |

### Jobs

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/provisioning/jobs/` | List all jobs | Network Engineer+ |
| POST | `/api/provisioning/jobs/` | Create and start a job | Network Engineer+ |
| GET | `/api/provisioning/jobs/{id}/` | Get job + per-device results | Network Engineer+ |

**POST /api/provisioning/jobs/ request body:**
```json
{
  "template": 1,
  "device_ids": [1, 2, 3],
  "variables": {
    "vlans": [
      {"id": 10, "name": "USERS", "ip_address": "10.0.10.1", "netmask": "255.255.255.0"},
      {"id": 20, "name": "SERVERS", "ip_address": "10.0.20.1", "netmask": "255.255.255.0"}
    ]
  }
}
```

### Audit Log

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/provisioning/audit/` | List all audit log entries | Any authenticated |
| GET | `/api/provisioning/audit/{id}/` | Get single entry | Any authenticated |

Query parameters: `?action=push_config`, `?success=true`, `?device=1`

---

## Audit Log

Every action that touches a device is recorded in `AuditLog`. It is:
- **Append-only** — no update or delete operations are exposed in any API
- **Indexed** on `(action, timestamp)` for fast filtering
- **Immutable** — the admin interface marks all fields as read-only

```json
{
  "id": 42,
  "action": "push_config",
  "actor_username": "john.doe",
  "device_hostname": "Core-SW",
  "detail": {
    "job_id": 7,
    "template": "VLAN Config",
    "variables": {"vlans": [{"id": 10, "name": "USERS"}]},
    "error": "",
    "duration_seconds": 4.23
  },
  "success": true,
  "ip_address": null,
  "timestamp": "2024-06-01T14:32:11Z"
}
```

---

## UI Pages

| URL | Template | Description |
|---|---|---|
| `/provisioning/` | `job_list.html` | Job history table + "New Job" modal |
| `/provisioning/jobs/{id}/` | `job_detail.html` | Per-device results, rendered config |
| `/provisioning/templates/` | `template_list.html` | Template card grid |
| `/provisioning/templates/{id}/` | `template_detail.html` | Template body + live Jinja2 preview |
| `/provisioning/audit/` | `audit_log.html` | Full audit log table |

---

## Usage Examples

### Create a template

```bash
curl -X POST http://localhost:8000/api/provisioning/templates/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OSPF Area 0",
    "template_type": "routing",
    "body": "router ospf {{ process_id }}\n router-id {{ router_id }}\n{% for net in networks %}\n network {{ net.ip }} {{ net.wildcard }} area {{ net.area }}\n{% endfor %}"
  }'
```

### Preview before pushing

```bash
curl -X POST http://localhost:8000/api/provisioning/templates/1/preview/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "process_id": 1,
      "router_id": "1.1.1.1",
      "networks": [{"ip": "10.0.0.0", "wildcard": "0.0.255.255", "area": 0}]
    }
  }'
```

### Push to multiple devices

```bash
curl -X POST http://localhost:8000/api/provisioning/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template": 1,
    "device_ids": [1, 2, 3],
    "variables": {
      "process_id": 1,
      "router_id": "1.1.1.1",
      "networks": [{"ip": "192.168.100.0", "wildcard": "0.0.0.255", "area": 0}]
    }
  }'
```

### Poll job status

```bash
# Check job status (poll until status is not "pending" or "running")
curl http://localhost:8000/api/provisioning/jobs/1/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Template has missing variable | `preview` returns `400`; job render raises before SSH connects |
| Template has Jinja2 syntax error | Caught at render time, job not created |
| SSH timeout | `NetmikoError` caught, `ProvisioningResult.error` set, job continues to next device |
| Wrong SSH credentials | `NetmikoError` caught, result marked failed, audit log entry written |
| Device partially configured (SSH drops mid-session) | Result marked failed with partial output |
| All devices fail | `job.status = "failed"` |
| Some devices fail | `job.status = "partial"` |
