# Security App

Automated security compliance checking and configuration drift detection for all network devices. Evaluates live running-configs against regex-based rules and compares them against golden-config baselines — both on demand and on a nightly Celery schedule.

---

## Models

### `ComplianceRule`

Defines a single security requirement evaluated by regex against a device's running-config.

| Field | Type | Description |
|-------|------|-------------|
| `id` | PK | Auto |
| `name` | CharField (unique) | Human name, e.g. `SSH v2 enabled` |
| `description` | TextField | What this rule checks and why |
| `category` | CharField | Grouping label: `SSH`, `AAA`, `NTP`, `SNMP`, `Logging`, etc. |
| `pattern` | CharField | Python regex searched against the full running-config |
| `match_means_pass` | BooleanField | `True` → pattern found = PASS (presence check); `False` → pattern found = FAIL (absence check) |
| `device_types` | JSONField (list) | Device type slugs this rule applies to. Empty list = all types |
| `severity` | CharField | `critical`, `warning`, or `info` |
| `is_active` | BooleanField | Inactive rules are skipped during checks |
| `remediation` | TextField | CLI commands that fix this finding |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

**Rule evaluation logic:**

```python
matched = bool(re.search(pattern, running_config, re.MULTILINE | re.IGNORECASE))
passes  = matched if match_means_pass else not matched
```

**Device type filtering:** `device_types` is a JSON array. An empty list means the rule runs on every device type. A rule with `["router", "l2_switch"]` is skipped for firewalls.

---

### `ComplianceResult`

One evaluation of one rule against one device at a point in time. Multiple runs accumulate — the UI always shows only the latest per `(device, rule)` pair.

| Field | Type | Description |
|-------|------|-------------|
| `id` | PK | Auto |
| `device` | FK → Device (CASCADE) | Target device |
| `rule` | FK → ComplianceRule (CASCADE) | Rule evaluated |
| `status` | CharField | `pass`, `fail`, `error`, `skipped` |
| `evidence` | TextField | First regex match (up to 500 chars), or empty string |
| `error_message` | TextField | Exception text if status is `error` |
| `checked_at` | DateTimeField | Auto-set on creation |
| `task_id` | CharField | Celery task UUID |

**Compliance score:** `pass_count / (pass + fail) × 100`. Errors and skipped are excluded. A device is **compliant** when its score ≥ 80%.

**Composite indexes:** `(device, rule, checked_at)` and `(device, status)`.

---

### `GoldenConfig`

The expected ("golden") running-config for a device type. One record per device type maximum (unique on `device_type`). Used as the baseline for drift detection.

| Field | Type | Description |
|-------|------|-------------|
| `id` | PK | Auto |
| `device_type` | CharField (unique) | Must match a `Device.device_type` slug |
| `name` | CharField | Display name |
| `description` | TextField | What this baseline covers |
| `content` | TextField | Expected config lines — one per line |
| `is_active` | BooleanField | Inactive baselines are skipped in drift checks |
| `version` | PositiveIntegerField | Manual version counter |
| `created_by` | FK → User (SET NULL) | Author (nullable) |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

---

### `DriftResult`

The result of comparing a device's actual running-config against its golden baseline. Records accumulate over time — the UI shows the latest per device plus a 20-entry history.

| Field | Type | Description |
|-------|------|-------------|
| `id` | PK | Auto |
| `device` | FK → Device (CASCADE) | Device checked |
| `golden_config` | FK → GoldenConfig (SET NULL) | Baseline used (nullable — baseline can be deleted) |
| `status` | CharField | `clean`, `drifted`, `error` |
| `diff` | TextField | Unified diff output (`golden → actual`) |
| `drift_lines` | IntegerField | Count of `+` and `-` lines in the diff |
| `running_config` | TextField | Full running-config snapshot (capped at 50 000 chars) |
| `error_message` | TextField | Exception text if status is `error` |
| `checked_at` | DateTimeField | Auto-set on creation |
| `task_id` | CharField | Celery task UUID |

**Composite indexes:** `(device, checked_at)` and `(device, status)`.

---

## Celery Tasks (`tasks.py`)

All tasks run on the **`default`** queue.

### `run_compliance_checks(device_id)` → `dict`

Evaluates all applicable active `ComplianceRule` objects against a single device.

**Steps:**

1. Load `Device` by `device_id`
2. Load all active `ComplianceRule` records
3. Filter rules to those applicable to `device.device_type` (`device_types` empty OR type in list)
4. SSH to device via Netmiko → `show running-config` (90 s read timeout)
5. Call `device.mark_seen()`
6. For each applicable rule:
   - `rule.evaluate(running_config)` → `True` / `False`
   - `rule.get_evidence(running_config)` → first matching line (≤ 500 chars)
   - Create `ComplianceResult(status=pass|fail)`
7. If SSH failed → all rules get status `error` with the exception message
8. Returns `{ device, pass, fail, error, skipped, score }`

Retries once after 15 s on transient errors. Auth failures are not retried.

---

### `run_all_compliance_checks()` → `dict`

Dispatches `run_compliance_checks` for every device with `status='up'` using a Celery `group` (parallel execution).

Returns `{ dispatched: N, group_id: "..." }`.

---

### `check_golden_config_drift(device_id)` → `dict`

Compares `show running-config` against the active `GoldenConfig` for the device's type.

**Steps:**

1. Load `Device` by `device_id`
2. Look up `GoldenConfig.objects.get(device_type=device.device_type, is_active=True)` — skip if none
3. SSH → `show running-config`
4. Normalise both sides: strip trailing whitespace, drop blank lines
5. `difflib.unified_diff(golden_lines, actual_lines, n=3)` with labelled fromfile/tofile
6. Count `+` and `-` lines → `drift_lines`
7. `status = clean` if `drift_lines == 0` else `drifted`
8. Create `DriftResult` with full diff and running-config snapshot
9. Returns `{ device, status, drift_lines }`

SSH failure creates a `DriftResult(status=error)` and returns immediately.

---

### `run_all_drift_checks()` → `dict`

Dispatches `check_golden_config_drift` for every UP device whose `device_type` has an active `GoldenConfig`. Uses Celery `group`.

Returns `{ dispatched: N, group_id: "..." }`.

---

## Views and URLs

All browser views are mounted under `/security/` with `app_name = 'security'`.

| URL | View | Auth | Description |
|-----|------|------|-------------|
| `/security/` | `security_home` | Login | Dashboard: overall score, per-device table, recent failures, drift summary |
| `/security/compliance/` | `compliance` | Login | All devices sorted by compliance score (worst first) |
| `/security/compliance/<device_id>/` | `compliance_device` | Login | Rule-by-rule breakdown for one device |
| `/security/drift/` | `drift_detection` | Login | Latest drift result per device, sorted by `drift_lines` desc |
| `/security/drift/<device_id>/` | `drift_device` | Login | Latest diff + last 20 drift check history for one device |

### `security_home` context

| Variable | Description |
|----------|-------------|
| `overall_score` | Global pass/total × 100 across all latest results |
| `total_checks` | Latest result count (one per device+rule pair) |
| `total_pass` / `total_fail` | Counts of latest results |
| `total_drifted` / `total_clean` | Latest drift result counts |
| `device_scores` | List of `{device, score, pass, total, fail}` sorted ascending (worst first) |
| `recent_fails` | Latest 10 failed compliance results |
| `rules_count` | Active rule count |

### "Latest result" query pattern

Both views and the compliance summary endpoint use the same pattern to avoid showing stale historical results alongside current ones:

```python
latest_ids = (
    ComplianceResult.objects
    .values('device', 'rule')
    .annotate(latest=Max('id'))
    .values_list('latest', flat=True)
)
qs = ComplianceResult.objects.filter(id__in=latest_ids)
```

This returns exactly one result per `(device, rule)` pair — the most recent check run.

---

## REST API

Mounted at both `/security/api/` and `/api/security/`.

### `ComplianceRuleViewSet` — full CRUD

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/rules/` | Login | List rules (filter: `is_active`, `severity`, `category`) |
| POST | `/api/rules/` | Engineer+ | Create rule |
| GET | `/api/rules/{id}/` | Login | Rule detail |
| PUT / PATCH | `/api/rules/{id}/` | Engineer+ | Update rule |
| DELETE | `/api/rules/{id}/` | Engineer+ | Delete rule |

Filters: `is_active`, `severity`, `category`. Search: `name`, `description`, `category`. Ordering: `name`, `category`, `severity`, `updated_at`.

---

### `ComplianceResultViewSet` — read-only

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/results/` | Login | All results (filter: `status`, `device`, `rule`, `rule__category`, `device__site`) |
| GET | `/api/results/{id}/` | Login | Single result detail |

Response includes flattened fields: `device_hostname`, `device_site`, `rule_name`, `rule_category`, `rule_severity`, `passed`.

---

### `GoldenConfigViewSet` — full CRUD

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/golden/` | Login | List golden configs (filter: `device_type`, `is_active`) |
| POST | `/api/golden/` | Engineer+ | Create baseline (`created_by` auto-set from JWT user) |
| GET | `/api/golden/{id}/` | Login | Detail |
| PUT / PATCH | `/api/golden/{id}/` | Engineer+ | Update |
| DELETE | `/api/golden/{id}/` | Engineer+ | Delete |

---

### `DriftResultViewSet` — read-only

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/drift/` | Login | All drift results (filter: `status`, `device`, `device__site`) |
| GET | `/api/drift/{id}/` | Login | Single result — includes full `diff` text |

Response includes: `device_hostname`, `device_site`, `device_type`, `golden_name`, `is_clean`.

---

### Functional endpoints

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/compliance/summary/` | Login | Aggregate stats for dashboard |
| POST | `/api/compliance/run/{device_id}/` | Engineer+ | Run compliance check on one device |
| POST | `/api/compliance/run-all/` | Engineer+ | Run compliance checks on all UP devices |
| POST | `/api/drift/run/{device_id}/` | Engineer+ | Run drift check on one device |
| POST | `/api/drift/run-all/` | Engineer+ | Run drift checks on all UP devices with a golden config |

All POST endpoints return `202 Accepted` with a `task_id`.

#### `GET /api/compliance/summary/` response

```json
{
  "overall_score":     85,
  "total_checks":      180,
  "total_pass":        153,
  "total_fail":        24,
  "total_error":       3,
  "devices_checked":   15,
  "devices_compliant": 12,
  "devices_drifted":   3,
  "last_checked":      "2026-06-17T02:00:14Z"
}
```

#### `POST /api/compliance/run/{device_id}/` response

```json
{ "task_id": "b2c4a1f0-...", "device_id": 7 }
```

---

## 12 Built-in Compliance Rules

Loaded from `fixtures/compliance_rules.json` on first `docker compose up`.

| Rule | Category | Severity | Check type | Pattern |
|------|----------|----------|------------|---------|
| SSH v2 enabled | SSH | Critical | Presence | `ip ssh version 2` |
| Telnet disabled | SSH | Critical | Absence | `transport input telnet` |
| AAA new-model | AAA | Critical | Presence | `aaa new-model` |
| No enable password | AAA | Critical | Absence | `enable password` |
| NTP server configured | NTP | Warning | Presence | `ntp server` |
| SNMP community with ACL | SNMP | Warning | Presence | `snmp-server community .+ \d+` |
| Syslog host configured | Logging | Warning | Presence | `logging host` |
| Service password-encryption | AAA | Warning | Presence | `service password-encryption` |
| OSPF MD5 authentication | Routing | Warning | Presence | `area .+ authentication message-digest` |
| CDP disabled on firewalls | Security | Warning | Absence | `no cdp run` (firewalls only) |
| Login banner present | Security | Info | Presence | `banner (login\|motd)` |
| Service timestamps log | Logging | Info | Presence | `service timestamps log` |

---

## Compliance Score Interpretation

| Score | Badge colour | Meaning |
|-------|-------------|---------|
| ≥ 80% | Green | Compliant |
| 50–79% | Yellow / Orange | Partially compliant — review failures |
| < 50% | Red | Non-compliant — immediate attention required |
| `None` | Grey | Never checked |

---

## Drift Detection Flow

```
[Run Drift] button / nightly Celery Beat (03:00)
  │
  └── check_golden_config_drift(device_id)  [default queue]
        │
        ├── GoldenConfig.objects.get(device_type=device.device_type)
        │     └── not found → skip, no DriftResult created
        │
        ├── Netmiko SSH → show running-config
        │     └── fail → DriftResult(status=error)
        │
        ├── Normalise: strip trailing whitespace, drop blank lines
        │
        ├── difflib.unified_diff(golden_lines, actual_lines, n=3)
        │
        ├── drift_lines = count(lines starting with + or -)
        │
        └── DriftResult(
              status      = 'clean' if drift_lines == 0 else 'drifted',
              diff        = '\n'.join(diff_lines),
              drift_lines = drift_lines,
              running_config = output[:50_000],
            )

Browser: /security/drift/<device_id>/
  - Latest diff rendered with green (+) / red (-) / blue (@) syntax colouring
  - History table of last 20 checks with timestamp and drift_lines count
```

---

## Permission Class

`IsEngineerOrReadOnly` — used across all write endpoints in the API:

| Method type | Required role |
|-------------|--------------|
| `GET`, `HEAD`, `OPTIONS` | Any authenticated user |
| `POST`, `PUT`, `PATCH`, `DELETE` | `engineer` or `admin` (or `is_superuser`) |

---

## Templates

| Template | Description |
|----------|-------------|
| `security/home.html` | Overall score gauge, per-device score table, recent failures, drift summary cards |
| `security/compliance.html` | All-devices compliance table with score bars; active rules list |
| `security/compliance_device.html` | Per-device rule-by-rule results: pass/fail badges, evidence text, severity icons |
| `security/drift.html` | Latest drift result per device: drift_lines count, status badge, link to detail |
| `security/drift_device.html` | Unified diff rendered with syntax colouring + 20-entry history table |

---

## Configuration

| Setting | Used by | Description |
|---------|---------|-------------|
| `CELERY_BROKER_URL` | Tasks | Redis broker |
| `CELERY_RESULT_BACKEND` | Tasks | Redis result backend |

No extra packages beyond the project baseline (`netmiko`, `celery`, `djangorestframework`, `django-filter`). Diffing uses Python's built-in `difflib`.

---

## Migrations

| Migration | Description |
|-----------|-------------|
| `0001_initial.py` | Creates `ComplianceRule`, `ComplianceResult`, `GoldenConfig`, `DriftResult` tables with all composite indexes |
