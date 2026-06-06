# Security & Compliance App (`apps/security`)

The Security app enforces network security policy through automated compliance checking, configuration drift detection, and role-based access control. It also provides the `UserProfile` model that implements platform RBAC.

---

## Table of Contents

- [Purpose](#purpose)
- [File Structure](#file-structure)
- [Data Models](#data-models)
- [Compliance Rules System](#compliance-rules-system)
- [Built-in Compliance Rules](#built-in-compliance-rules)
- [Configuration Drift Detection](#configuration-drift-detection)
- [Role-Based Access Control](#role-based-access-control)
- [Celery Tasks](#celery-tasks)
- [REST API Reference](#rest-api-reference)
- [UI Pages](#ui-pages)
- [Usage Examples](#usage-examples)

---

## Purpose

- Define compliance rules that describe what a secure network device looks like
- Automatically check devices against those rules by sending show commands over SSH and matching output with regex
- Detect when a device's running configuration has drifted from its approved "golden" snapshot
- Provide role-based access control that controls who can read, push, or administer the platform
- Record all compliance and drift results in the database for trending and reporting

---

## File Structure

```
apps/security/
├── models.py              # ComplianceRule, ComplianceCheck, ConfigSnapshot, DriftReport, UserProfile
├── serializers.py         # DRF serializers for all models
├── views.py               # ViewSets + SecurityActionViewSet (fire-and-forget actions)
├── urls.py                # API router: /api/security/
├── ui_urls.py             # Browser URL patterns: /security/
├── ui_views.py            # Django template views
├── compliance_checks.py   # Rule evaluator + BUILTIN_RULES list
├── tasks.py               # Celery tasks: compliance check, drift detection, snapshot
├── admin.py               # Django admin registration
├── apps.py                # AppConfig
└── management/
    └── commands/
        └── seed_compliance_rules.py   # Idempotent rule seeding command
```

---

## Data Models

### `ComplianceRule`

Defines a single security check to run on a device.

| Field | Type | Description |
|---|---|---|
| `name` | CharField(255) | Unique rule name |
| `description` | TextField | What this rule checks |
| `check_command` | CharField(255) | IOS exec command to run (e.g. `show ip ssh`) |
| `expected_pattern` | CharField(512) | Python regex applied to the command output |
| `must_match` | BooleanField | `True` = pattern must match. `False` = pattern must NOT match |
| `severity` | CharField | `critical`, `high`, `medium`, `low` |
| `remediation` | TextField | Jinja2 config snippet to fix the violation |
| `is_active` | BooleanField | Inactive rules are skipped during checks |
| `created_at` | DateTimeField | Auto-set |

**How the evaluator works:**
```python
def evaluate_rule(output: str, pattern: str, must_match: bool) -> bool:
    matched = bool(re.search(pattern, output, re.MULTILINE | re.IGNORECASE))
    return matched if must_match else not matched
```

- `must_match=True`: Device is compliant if the pattern **is found** in the output
  - Example: "SSH v2 Enabled" → output must contain `SSH Enabled - version 2.0`
- `must_match=False`: Device is compliant if the pattern is **not found** in the output
  - Example: "Telnet Disabled" → output must NOT contain `transport input telnet`

### `ComplianceCheck`

A single evaluation result — one rule checked against one device at one point in time.

| Field | Type | Description |
|---|---|---|
| `device` | FK(Device) | Checked device |
| `rule` | FK(ComplianceRule) | Which rule was applied |
| `status` | CharField | `compliant`, `non_compliant`, `error` |
| `output` | TextField | First 4000 chars of command output |
| `detail` | TextField | Human-readable explanation of why it failed |
| `checked_at` | DateTimeField | When the check ran |
| `initiated_by` | FK(User) | Who triggered the check |

**Database index:** `(device, rule, checked_at)` — supports "latest check per device per rule" queries.

### `ConfigSnapshot`

A point-in-time capture of a device's full running configuration.

| Field | Type | Description |
|---|---|---|
| `device` | FK(Device) | Source device |
| `config` | TextField | Full `show running-config` output |
| `is_golden` | BooleanField | Whether this is the approved baseline |
| `taken_at` | DateTimeField | When captured |
| `taken_by` | FK(User) | Who triggered the snapshot |
| `comment` | CharField | Optional label |

**Golden config:** Each device has at most one golden snapshot at a time. When you call `set_golden` on a snapshot, all others for that device are set to `is_golden=False`.

### `DriftReport`

The result of comparing a device's current config against its golden snapshot.

| Field | Type | Description |
|---|---|---|
| `device` | FK(Device) | Checked device |
| `golden_snapshot` | FK(ConfigSnapshot) | The approved baseline |
| `current_snapshot` | FK(ConfigSnapshot) | The freshly captured config |
| `status` | CharField | `clean`, `drifted`, `error` |
| `diff` | TextField | `unified_diff` output (first 10000 chars) |
| `checked_at` | DateTimeField | When drift detection ran |

### `UserProfile`

Extends Django's `User` model with a platform role.

| Field | Type | Description |
|---|---|---|
| `user` | OneToOneField(User) | The Django user |
| `role` | CharField | `admin`, `network_engineer`, `read_only` |
| `created_at` | DateTimeField | Auto-set |

**Signal to auto-create:** No signal is implemented — profiles are created explicitly by an admin via the admin interface or API. New users get no profile (defaults to read-only behavior in permission checks).

---

## Compliance Rules System

### Evaluator

`compliance_checks.py` contains the `evaluate_rule()` function and the `BUILTIN_RULES` list.

The evaluation is **pure and side-effect free** — it only receives text output and returns a boolean. All side effects (SSH, database writes) are in the Celery task.

### Seeding built-in rules

```bash
# Run once (or on every deploy — it is idempotent)
python manage.py seed_compliance_rules

# Or via Docker
docker compose exec django python manage.py seed_compliance_rules
```

The command uses `update_or_create` keyed on `name`, so running it multiple times is safe.

---

## Built-in Compliance Rules

| Rule Name | Severity | Command | Check |
|---|---|---|---|
| SSH v2 Enabled | Critical | `show ip ssh` | Output contains `SSH Enabled - version 2.0` |
| Telnet Disabled on VTY | Critical | `show running-config \| section line vty` | Output does NOT contain `transport input telnet` |
| SNMP v3 Configured | High | `show running-config \| include snmp-server user` | Output contains `snmp-server user .+ v3` |
| ACL on VTY Lines | High | `show running-config \| section line vty` | Output contains `access-class \S+ in` |
| Service Password Encryption | High | `show running-config \| include service password-encryption` | Output contains `service password-encryption` |
| HTTP Server Disabled | Medium | `show running-config \| include ip http server` | Output does NOT contain `ip http server` (only `no ip http`) |
| Logging Enabled | Medium | `show running-config \| include logging buffered` | Output contains `logging buffered` |
| Banner MOTD Configured | Low | `show running-config \| include banner motd` | Output contains `banner motd` |

Each non-compliant result includes a `detail` string explaining what was expected vs. what was found, and a `remediation` Jinja2 snippet that can be pushed via the provisioning app to fix it.

---

## Configuration Drift Detection

Drift detection compares a device's current running configuration against a stored "golden" baseline.

### Workflow

```
1. Take initial snapshot → mark as golden
   POST /api/security/actions/snapshot/take/
   Body: {"device_id": 1, "set_golden": true}

2. (Later) Run drift detection
   POST /api/security/actions/drift/run/
   Body: {"device_id": 1}

3. Task executes:
   a. SSH → show running-config → save as ConfigSnapshot (current)
   b. Load latest golden ConfigSnapshot for this device
   c. unified_diff(golden.config, current.config)
   d. Save DriftReport with status="clean" or "drifted" and the diff text

4. View result:
   GET /api/security/drift/?device=1
   Or: /security/drift/{id}/  (shows colored unified diff)
```

### First-time behavior

If no golden snapshot exists for a device, the task automatically promotes the current snapshot as golden and returns `status: "clean"`. This seeds the baseline on first run.

### Diff format

The diff is stored as unified diff format (same as `git diff`):

```diff
--- golden (2024-01-01)
+++ current (2024-06-01)
@@ -45,4 +45,4 @@
 !
-no cdp run
+cdp run
 !
```

The UI renders this with color: green for additions, red for deletions, blue for hunk headers.

---

## Role-Based Access Control

### Roles

| Role | Description |
|---|---|
| `admin` | Full access to everything including user management |
| `network_engineer` | Can read, push configs, run compliance checks, take snapshots |
| `read_only` | Can only read inventory, monitoring, and compliance results |

### Permission classes (defined in `apps/inventory/permissions.py`)

| Class | Grants access to |
|---|---|
| `ReadOnlyOrAbove` | All authenticated users for GET; `network_engineer`+ for mutations |
| `IsAdminOrNetworkEngineer` | `network_engineer` or `admin` for all methods |
| `IsAdminOnly` | `admin` or Django superuser only |

### Assigning roles

**Via Django admin:**
1. Go to `http://localhost:8000/admin/security/userprofile/`
2. Click a profile to change the role

**Via API (admin only):**
```bash
curl -X PATCH http://localhost:8000/api/security/users/1/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "network_engineer"}'
```

**Creating a profile for a new user:**
```bash
# First create the Django user via admin panel, then:
curl -X POST http://localhost:8000/api/security/users/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user": 2, "role": "read_only"}'
```

---

## Celery Tasks

All tasks run on the `compliance` queue.

### `run_compliance_check(device_id, rule_ids=None, initiated_by_id=None)`

- Connects to the device via SSH
- Runs each active `ComplianceRule.check_command`
- Evaluates output with `evaluate_rule()`
- Saves a `ComplianceCheck` record per rule
- Writes one `AuditLog` entry summarizing all results
- `rule_ids=None` means check all active rules

### `run_drift_detection(device_id, initiated_by_id=None)`

- Connects via SSH → captures running config
- Saves as `ConfigSnapshot`
- Finds latest golden snapshot
- Runs `unified_diff`
- Saves `DriftReport`
- Returns `{"status": "clean"/"drifted", "drift": true/false}`

### `take_config_snapshot(device_id, set_golden=False, initiated_by_id=None)`

- Captures running config
- Saves as `ConfigSnapshot`
- If `set_golden=True`: marks as golden (does NOT automatically unset others — use `set_golden` API action)
- Writes `AuditLog` entry

---

## REST API Reference

Base path: `/api/security/`

### Compliance Rules

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/security/rules/` | List all rules | Network Engineer+ |
| POST | `/api/security/rules/` | Create custom rule | Network Engineer+ |
| GET | `/api/security/rules/{id}/` | Rule detail | Network Engineer+ |
| PUT/PATCH | `/api/security/rules/{id}/` | Update rule | Network Engineer+ |
| DELETE | `/api/security/rules/{id}/` | Delete rule | Network Engineer+ |

### Compliance Checks (read-only results)

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/security/checks/` | List all results | Any authenticated |
| GET | `/api/security/checks/{id}/` | Single result | Any authenticated |

Query: `?device=1`, `?rule=2`, `?status=non_compliant`

### Config Snapshots

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/security/snapshots/` | List all snapshots | Any authenticated |
| GET | `/api/security/snapshots/{id}/` | Snapshot detail + config | Any authenticated |
| POST | `/api/security/snapshots/{id}/set_golden/` | Promote to golden | Network Engineer+ |

### Drift Reports

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/security/drift/` | List all reports | Any authenticated |
| GET | `/api/security/drift/{id}/` | Report detail + diff | Any authenticated |

### Security Actions (fire-and-forget)

| Method | Endpoint | Body | Description |
|---|---|---|---|
| POST | `/api/security/actions/compliance/run/` | `{"device_id": 1, "rule_ids": [1,2]}` | Run compliance check async |
| POST | `/api/security/actions/drift/run/` | `{"device_id": 1}` | Run drift detection async |
| POST | `/api/security/actions/snapshot/take/` | `{"device_id": 1, "set_golden": true}` | Take config snapshot |

All action endpoints return `{"task_id": "celery-uuid"}` immediately.

### User Profiles (admin only)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/security/users/` | List all profiles |
| POST | `/api/security/users/` | Create profile for a user |
| PATCH | `/api/security/users/{id}/` | Update role |

---

## UI Pages

| URL | Template | Description |
|---|---|---|
| `/security/` | `compliance_dashboard.html` | Summary cards: compliant/non-compliant/drifted + recent results |
| `/security/checks/` | `compliance_checks.html` | Full compliance check table |
| `/security/drift/` | `drift_reports.html` | All drift reports with status |
| `/security/drift/{id}/` | `drift_detail.html` | Colored unified diff view |

---

## Usage Examples

### Run compliance check on a device

```bash
curl -X POST http://localhost:8000/api/security/actions/compliance/run/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1}'
```

### Run only critical rules

```bash
# First, find the IDs of critical rules
curl "http://localhost:8000/api/security/rules/?severity=critical" \
  -H "Authorization: Bearer $TOKEN"

# Then run only those rules
curl -X POST http://localhost:8000/api/security/actions/compliance/run/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1, "rule_ids": [1, 2]}'
```

### Take a golden config snapshot

```bash
curl -X POST http://localhost:8000/api/security/actions/snapshot/take/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1, "set_golden": true}'
```

### Run drift detection

```bash
curl -X POST http://localhost:8000/api/security/actions/drift/run/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1}'
```

### Get all non-compliant checks

```bash
curl "http://localhost:8000/api/security/checks/?status=non_compliant" \
  -H "Authorization: Bearer $TOKEN"
```

### Promote a snapshot to golden

```bash
curl -X POST http://localhost:8000/api/security/snapshots/5/set_golden/ \
  -H "Authorization: Bearer $TOKEN"
```

### Add a custom compliance rule

```bash
curl -X POST http://localhost:8000/api/security/rules/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "NTP Configured",
    "description": "NTP server must be configured for time synchronization",
    "check_command": "show running-config | include ntp server",
    "expected_pattern": "ntp server",
    "must_match": true,
    "severity": "medium",
    "remediation": "ntp server 192.168.100.254"
  }'
```
