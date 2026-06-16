# Provisioning App

Renders Jinja2 config templates and pushes them to network devices over SSH via Netmiko and Celery. Includes a full audit trail of every push, a web UI for managing `.j2` file templates, and a one-click running-config download.

---

## Models

### `ProvisioningTemplate`

Stores config templates in the database (alternative to file-based `.j2` files).

| Field        | Type          | Description                                   |
|--------------|---------------|-----------------------------------------------|
| `name`       | CharField     | Unique template identifier; used as the lookup key |
| `description`| TextField     | Human-readable description                    |
| `device_type`| CharField     | Optional filter: router, firewall, switch, etc.|
| `site`       | CharField     | Optional filter: sofia, burgas, plovdiv        |
| `content`    | TextField     | Jinja2 template source                        |
| `is_active`  | BooleanField  | Inactive templates are excluded from the engine|
| `created_by` | FK → User     | Auto-set on creation                          |
| `created_at` | DateTimeField | Auto-set on creation                          |
| `updated_at` | DateTimeField | Auto-updated on save                          |

---

### `AuditLog`

Every config push and running-config pull is recorded here.

| Field           | Type          | Description                                        |
|-----------------|---------------|----------------------------------------------------|
| `device`        | FK → Device   | Target device (cascades on delete)                 |
| `user`          | FK → User     | Who triggered the operation (nullable)             |
| `template_name` | CharField     | Template used (or `running-config` for pulls)      |
| `action`        | CharField     | Human label, e.g. `Push ssh_hardening` or `Pull running-config` |
| `config_sent`   | TextField     | Rendered config that was pushed (or pulled output) |
| `config_diff`   | TextField     | Unified diff: running-config before vs after push  |
| `status`        | CharField     | `pending`, `success`, `failed`                     |
| `error_message` | TextField     | Exception text if status is `failed`               |
| `task_id`       | CharField     | Celery task UUID for cross-referencing             |
| `execution_time`| FloatField    | Seconds from connect to disconnect                 |
| `timestamp`     | DateTimeField | Auto-set when the record is created                |

---

## Template Engine (`template_engine.py`)

A custom Jinja2 environment that merges two sources, DB first:

```
ChoiceLoader
  ├── DBLoader       → ProvisioningTemplate.objects.get(name=..., is_active=True)
  └── FileSystemLoader → config_templates/*.j2
```

Templates are looked up by name. If a DB template and a file template share the same name, the DB version wins.

**Environment settings:** `trim_blocks=True`, `lstrip_blocks=True`, `keep_trailing_newline=True`, `autoescape=False` (network configs are not HTML).

### Standard template context

These variables are available in every template:

| Variable         | Source                              |
|------------------|-------------------------------------|
| `hostname`       | `device.hostname`                   |
| `ip_address`     | `device.ip_address`                 |
| `wan_ip`         | `device.wan_ip` (empty string if unset) |
| `loopback_ip`    | `device.loopback_ip`                |
| `site`           | `device.site` (e.g. `sofia`)        |
| `site_label`     | `device.get_site_display()`         |
| `device_type`    | `device.device_type`                |
| `vendor`         | `device.vendor`                     |
| `model`          | `device.model`                      |
| `os_version`     | `device.os_version`                 |
| `snmp_community` | `device.snmp_community`             |
| `ssh_username`   | `device.ssh_username`               |
| `MGMT_NETWORK`   | `192.168.100.0/24`                  |
| `NTP_SERVER`     | `192.168.100.1`                     |
| `SYSLOG_SERVER`  | `192.168.100.1`                     |

Extra context can be passed per-push via the API (`extra_context` field).

### Custom filters

| Filter    | Behaviour              |
|-----------|------------------------|
| `upper`   | `str.upper`            |
| `lower`   | `str.lower`            |

---

## Built-in File Templates

Nine `.j2` files ship in `config_templates/`:

| File                        | Purpose                                                     |
|-----------------------------|-------------------------------------------------------------|
| `ssh_hardening.j2`          | SSH v2, disable Telnet/HTTP, VTY access-class, AAA, password policy |
| `ospf_area0.j2`             | OSPF process, area 0, passive interfaces, loopback network  |
| `router_ospf_loopback.j2`   | Router loopback + OSPF redistribute connected               |
| `firewall_primary_wan.j2`   | WAN-facing ACL and NAT rules for primary firewall           |
| `ntp_syslog.j2`             | NTP server, timezone, syslog destination and severity       |
| `snmp_v2c.j2`               | SNMPv2c community, location, contact, trap host             |
| `acl_management.j2`         | Management-plane ACL restricting access to `MGMT_NETWORK`   |
| `interface_descriptions.j2` | Bulk interface description assignments per device type      |
| `vlan_access.j2`            | Access-port VLAN assignment and spanning-tree portfast      |

---

## Celery Tasks (`tasks.py`)

All tasks run on the `provisioning` queue unless noted.

### `push_config_to_device(device_id, template_name, extra_context, user_id, dry_run)`

Single-device config push:

1. Load device and optional user from DB
2. Render the Jinja2 template via `render_template()`
3. Open a Netmiko `ConnectHandler` using `device.get_netmiko_params()`
4. Capture running-config **before** (`show running-config`)
5. Send rendered commands via `send_config_set()`
6. `save_config()`
7. Capture running-config **after**
8. Generate unified diff (before vs after)
9. Write `AuditLog` record (success or failed)
10. Call `device.mark_seen()`

In **dry-run** mode steps 3–8 are skipped; the rendered config is returned and logged without touching the device.

Retries once on transient errors; auth failures are not retried.

---

### `push_config_to_devices(device_ids, template_name, extra_context, user_id, dry_run)`

Dispatches a Celery `group` of `push_config_to_device` tasks — all devices run in parallel. Returns a group ID and device count.

---

### `pull_running_config(device_id, user_id)`

Pulls the current running configuration from a single device:

1. SSH via Netmiko → `show running-config`
2. Calls `device.mark_seen()`
3. Writes `AuditLog` record with `action='Pull running-config'`
4. Returns `{ config, hostname, site, timestamp }` in the Celery result

The task result is stored in Redis and consumed by the download view. Retries once on transient errors; auth failures are not retried.

---

### `render_preview(device_id, template_name, extra_context)`

Queue: `default`. Renders a template for a device and returns the result without connecting to the device. Used by the push-config UI preview.

---

## Views and URLs

All URLs are mounted under `/provisioning/` with `app_name = 'provisioning'`.

### Browser views

| URL                                        | View                       | Auth      | Description                              |
|--------------------------------------------|----------------------------|-----------|------------------------------------------|
| `/provisioning/`                           | `provisioning_home`        | Login     | Stats, template library, recent activity |
| `/provisioning/push/`                      | `push_config`              | Engineer+ | Push config to devices                   |
| `/provisioning/audit/`                     | `audit_log`                | Login     | Filterable audit log (search, status, site, page) |
| `/provisioning/audit/<pk>/`                | `audit_detail`             | Login     | Full detail of one audit entry           |
| `/provisioning/pull-config/<task_id>/download/` | `pull_config_download_view` | Login | Serve completed running-config as `.txt` download |

### File template management

| URL                                             | View                    | Auth      | Description                          |
|-------------------------------------------------|-------------------------|-----------|--------------------------------------|
| `/provisioning/file-templates/`                 | `file_template_list`    | Engineer+ | Table of all `.j2` files             |
| `/provisioning/file-templates/new/`             | `file_template_create`  | Engineer+ | Create a new `.j2` file              |
| `/provisioning/file-templates/<stem>/`          | `file_template_detail`  | Login     | Read-only view of file content       |
| `/provisioning/file-templates/<stem>/edit/`     | `file_template_edit`    | Engineer+ | Edit and save file content           |
| `/provisioning/file-templates/<stem>/delete/`   | `file_template_delete`  | Engineer+ | POST-only delete                     |

**Security:** filenames are validated against `^[a-z0-9_\-]+$` before any disk operation. Jinja2 syntax is validated with `Environment().parse()` before the file is written — broken templates are rejected with the exact error line.

---

## REST API

Mounted at both `/provisioning/api/` and `/api/provisioning/`.

### Template CRUD — `ProvisioningTemplateViewSet`

| Method | URL                              | Description                        |
|--------|----------------------------------|------------------------------------|
| GET    | `/api/templates/`                | List active DB templates           |
| POST   | `/api/templates/`                | Create template (engineer+)        |
| GET    | `/api/templates/<id>/`           | Template detail                    |
| PUT    | `/api/templates/<id>/`           | Full update (engineer+)            |
| PATCH  | `/api/templates/<id>/`           | Partial update (engineer+)         |
| DELETE | `/api/templates/<id>/`           | Delete (engineer+)                 |
| GET    | `/api/templates/all-names/`      | Combined list of DB + file templates for dropdowns |

Filters: `device_type`, `site`, `is_active`. Search: `name`, `description`. Ordering: `name`, `updated_at`, `device_type`.

### Audit log — `AuditLogViewSet` (read-only)

| Method | URL                | Description                                    |
|--------|--------------------|------------------------------------------------|
| GET    | `/api/audit/`      | Paginated audit log                            |
| GET    | `/api/audit/<id>/` | Single entry detail                            |

Filters: `status`, `device__site`, `device`. Search: `device__hostname`, `template_name`, `action`, `user__username`.

### Functional endpoints

| Method | URL                          | Description                                                  |
|--------|------------------------------|--------------------------------------------------------------|
| POST   | `/api/render/`               | Render a template for a device without pushing; returns rendered text |
| POST   | `/api/push/`                 | Dispatch push task(s); returns `task_id`                     |
| POST   | `/api/pull-config/`          | Trigger `pull_running_config` task; returns `task_id`        |
| GET    | `/api/task/<task_id>/`       | Poll Celery task state and result                            |

#### `POST /api/push/` body

```json
{
  "device_ids":    [1, 2, 3],
  "template_name": "ssh_hardening.j2",
  "dry_run":       false,
  "extra_context": { "custom_var": "value" }
}
```

#### `POST /api/pull-config/` body

```json
{ "device_id": 3 }
```

Returns `{ "task_id": "abc-123", "device": "sofia-r1", "status": "queued" }`. Poll `/api/task/<task_id>/` until `state == "SUCCESS"`, then redirect to `/provisioning/pull-config/<task_id>/download/`.

### Permission class — `IsEngineerOrReadOnly`

`GET` requests: any authenticated user. `POST/PUT/PATCH/DELETE`: engineer or admin role only.

---

## Pull Running Config — End-to-End

```
Device detail page
  │
  [Pull Config] button (engineer only)
  │
  POST /provisioning/api/pull-config/  { device_id }
  │
  Celery: pull_running_config(device_id, user_id)
    ├── Netmiko SSH → show running-config
    ├── AuditLog.create(action='Pull running-config', status='success')
    └── return { config, hostname, site, timestamp }
  │
  Browser polls /provisioning/api/task/<task_id>/ every 2 s (timeout: 30 s)
  │
  state == SUCCESS
  │
  window.location = /provisioning/pull-config/<task_id>/download/
  │
  HttpResponse(config_text, content_type='text/plain')
  Content-Disposition: attachment; filename="sofia_sofia-r1_running-config_2026-06-17_23-47.txt"
```

The config is never written to disk — it is served directly from the Celery task result stored in Redis.

---

## File Template Editor — Features

- **Jinja2 syntax validation** before saving (error shown with line number)
- **Variable chips** sidebar — click any variable to insert `{{ variable }}` at cursor
- **Tab key** inserts a space instead of leaving the textarea
- **Live line counter** updates as you type
- **Copy button** on the detail view copies content to clipboard

---

## Templates

| Template                                        | Description                                         |
|-------------------------------------------------|-----------------------------------------------------|
| `provisioning/home.html`                        | Stats cards, template library, recent activity log  |
| `provisioning/push_config.html`                 | Device/template selector, dry-run toggle, push UI   |
| `provisioning/audit_log.html`                   | Filterable table with search, status, site, pagination |
| `provisioning/audit_detail.html`                | Full audit entry: config sent, diff, error, metadata|
| `provisioning/file_template_list.html`          | Table of `.j2` files with inline delete modal       |
| `provisioning/file_template_form.html`          | Shared create/edit form with variable sidebar       |
| `provisioning/file_template_detail.html`        | Read-only code view with copy button and delete overlay |

---

## Configuration

| Setting         | Used by                  | Description                                         |
|-----------------|--------------------------|-----------------------------------------------------|
| `CELERY_BROKER_URL` | All tasks            | Redis (or other) broker URL                         |
| `CELERY_RESULT_BACKEND` | `task_status_view`, download view | Where task results are stored — must be Redis for the pull-config download flow |

No extra packages beyond what is already in the project (`netmiko`, `jinja2`, `celery`, `djangorestframework`).

---

## Migrations

| Migration        | Description                                      |
|------------------|--------------------------------------------------|
| `0001_initial.py`| Creates `ProvisioningTemplate` and `AuditLog`    |
