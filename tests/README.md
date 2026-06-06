# Test Suite (`tests/`)

The test suite covers all four application modules using pytest with Django. Tests use real PostgreSQL and Redis — no mocking of the database or cache layer.

---

## File Structure

```
tests/
├── __init__.py
├── test_inventory.py     # Device CRUD, discovery job API
├── test_provisioning.py  # Jinja2 rendering, template API, preview
├── test_monitoring.py    # AlertManager webhook, alert list, acknowledge
└── test_security.py      # Compliance evaluator, rule seeding, rule API
```

---

## Running the Tests

### Prerequisites

Services must be running (or accessible) before running tests:

```bash
# Start all services
docker compose up -d postgres redis

# Or run inside the Django container (has everything available)
docker compose exec django bash
```

### Basic run

```bash
pytest
```

### With coverage report

```bash
pytest --cov=apps --cov=devsecops_platform --cov-report=term-missing
```

### Verbose output with short tracebacks

```bash
pytest -v --tb=short
```

### Run one test file

```bash
pytest tests/test_inventory.py -v
```

### Run one specific test

```bash
pytest tests/test_inventory.py::TestDeviceAPI::test_create_device -v
```

### Run tests matching a keyword

```bash
pytest -k "compliance" -v
```

---

## Test Configuration — `pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = devsecops_platform.settings
addopts = -v --tb=short
```

`DJANGO_SETTINGS_MODULE` tells pytest-django which settings to use. The settings read from the `.env` file, so a valid `.env` must exist.

For CI, environment variables are set directly in the GitHub Actions workflow — no `.env` file needed there.

---

## Test Files

### `test_inventory.py` — Inventory API

**Test class: `TestDeviceAPI`**

Tests the `/api/inventory/devices/` REST API endpoint.

| Test | What it verifies |
|---|---|
| `test_unauthenticated_returns_401` | Requests without JWT are rejected |
| `test_list_devices` | GET returns device list with correct fields |
| `test_create_device` | POST creates a device and returns 201 |
| `test_create_duplicate_ip_returns_400` | Second device with same IP returns 400 |
| `test_retrieve_device` | GET `/devices/{id}/` returns device detail |
| `test_update_device` | PATCH updates allowed fields |
| `test_delete_device` | DELETE removes the device |
| `test_filter_by_status` | `?status=online` filters correctly |
| `test_search_by_hostname` | `?search=R1` returns matching devices |

**Test class: `TestDiscoveryAPI`**

Tests the `/api/inventory/discovery/` endpoint.

| Test | What it verifies |
|---|---|
| `test_start_discovery_job` | POST creates a DiscoveryJob and returns task_id |
| `test_list_discovery_jobs` | GET returns all jobs with status |

**Setup:**
- Creates a `User` and `UserProfile` (role: `network_engineer`) in `setUpTestData`
- Gets JWT access token via `/api/auth/token/`
- Sets `Authorization: Bearer <token>` header on the test client

---

### `test_provisioning.py` — Provisioning

**Test class: `TestJinjaRenderer`**

Unit tests for the Jinja2 template renderer in `apps/provisioning/jinja_renderer.py`. No database, no HTTP — pure function testing.

| Test | What it verifies |
|---|---|
| `test_render_simple_template` | `{{ hostname }}` renders correctly |
| `test_render_loop_template` | `{% for vlan in vlans %}` iterates correctly |
| `test_missing_variable_raises_value_error` | `StrictUndefined` causes `ValueError` on missing var |
| `test_syntax_error_raises_value_error` | `{% if %}` without `{% endif %}` raises `ValueError` |

**Test class: `TestConfigTemplateAPI`**

Tests the `/api/provisioning/templates/` endpoint.

| Test | What it verifies |
|---|---|
| `test_list_templates` | GET returns all templates |
| `test_create_template` | POST creates template with body and type |
| `test_preview_template` | POST to preview endpoint with variables returns rendered output |
| `test_preview_missing_variable_returns_400` | Preview with missing variable returns 400 |

---

### `test_monitoring.py` — Monitoring / AlertManager

**Test class: `TestAlertManagerWebhook`**

Tests the `/api/monitoring/webhook/alertmanager/` endpoint.

| Test | What it verifies |
|---|---|
| `test_webhook_creates_alert` | POST with AlertManager v4 payload creates Alert record |
| `test_webhook_deduplicates_by_fingerprint` | Second POST with same fingerprint updates, not creates |
| `test_webhook_resolved_status` | Payload with `status: resolved` sets `Alert.status = "resolved"` |
| `test_list_alerts` | GET `/api/monitoring/alerts/` returns alert list |
| `test_acknowledge_alert` | PATCH sets `acknowledged=True` and `acknowledged_at` |

**AlertManager payload format used in tests:**
```json
{
  "version": "4",
  "alerts": [{
    "status": "firing",
    "labels": {"alertname": "InterfaceDown", "severity": "critical", "instance": "192.168.100.1:161"},
    "annotations": {"summary": "Interface is down"},
    "startsAt": "2024-01-01T00:00:00Z",
    "endsAt": "0001-01-01T00:00:00Z",
    "fingerprint": "abc123def456"
  }]
}
```

The webhook endpoint has `AllowAny` permission so the test client does not need a JWT token.

---

### `test_security.py` — Security and Compliance

**Test class: `TestComplianceEvaluator`**

Unit tests for `evaluate_rule()` in `apps/security/compliance_checks.py`. No database, no HTTP.

| Test | What it verifies |
|---|---|
| `test_ssh_v2_compliant` | Output containing "SSH Enabled - version 2.0" → compliant |
| `test_ssh_v2_non_compliant` | Output containing "SSH Enabled - version 1.99" → non-compliant |
| `test_telnet_disabled_compliant` | Output without "transport input telnet" → compliant |
| `test_telnet_disabled_non_compliant` | Output with "transport input telnet" → non-compliant |
| `test_all_builtin_rules_have_required_fields` | Every rule in `BUILTIN_RULES` has name, command, pattern, severity |
| `test_builtin_rule_severities_are_valid` | All severities are in `{critical, high, medium, low}` |

**Test class: `TestComplianceRuleAPI`**

Tests rule seeding and the `/api/security/rules/` API.

| Test | What it verifies |
|---|---|
| `test_seed_command_creates_rules` | `seed_compliance_rules` creates 8 rules |
| `test_seed_command_is_idempotent` | Running twice does not create duplicates |
| `test_list_compliance_rules` | GET returns seeded rules with correct fields |

---

## Fixtures and Test Data

Tests use Django's `TestCase.setUpTestData()` for shared setup within a class. Data created there is wrapped in a savepoint and rolled back between tests.

**Common setup pattern:**
```python
@classmethod
def setUpTestData(cls):
    cls.user = User.objects.create_user(username="engineer", password="pass")
    cls.profile = UserProfile.objects.create(user=cls.user, role="network_engineer")

def setUp(self):
    response = self.client.post("/api/auth/token/", {"username": "engineer", "password": "pass"})
    self.token = response.data["access"]
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
```

---

## Coverage

Current test coverage targets:

| Module | Coverage target |
|---|---|
| `apps/inventory/` | 80%+ |
| `apps/provisioning/` | 85%+ (Jinja2 unit tests boost this) |
| `apps/monitoring/` | 75%+ |
| `apps/security/` | 80%+ |
| `devsecops_platform/` | 60%+ |

Run coverage locally:
```bash
pytest --cov=apps --cov=devsecops_platform --cov-report=html
open htmlcov/index.html
```

---

## What is NOT tested

Tests that would require a live EVE-NG network are not included:

- Netmiko SSH connection to real devices (`test_provisioning.py` tests the renderer only)
- SNMP queries to real devices
- Celery task execution (Celery is configured with `task_always_eager=True` in test settings to run tasks synchronously)

For integration testing against real devices, run the platform against the EVE-NG topology and verify results via the UI or API.

---

## Troubleshooting

**`django.db.utils.OperationalError: could not connect to server`**

PostgreSQL is not running or `POSTGRES_HOST` is wrong. Start it:
```bash
docker compose up -d postgres
```

**`ImportError: No module named 'apps.inventory'`**

Run pytest from the project root directory (where `manage.py` is), not from inside `tests/`.

**`AssertionError: 401 != 200` on all tests**

JWT authentication is failing. Check that the `User` was created with `create_user()` (which hashes the password), not `User(username=..., password=...)` (which stores it in plaintext and causes auth to fail).
