# CLI App

Browser-based SSH terminal for network devices. Provides two parallel interfaces: a **live WebSocket terminal** (xterm.js + Paramiko) for fully interactive sessions, and a **REST + Celery command API** for scripted/async command execution with persistent history.

---

## Architecture

```
Browser
  │
  ├── WebSocket /ws/cli/<pk>/          ← live terminal (xterm.js ↔ Paramiko)
  │       │
  │       └── SSHConsumer (Django Channels, async)
  │               └── Paramiko SSH → device
  │
  └── REST API /api/cli/execute/       ← async command execution
          │
          └── Celery task: execute_cli_command
                  └── Netmiko SSH → device → CLICommand saved to DB
```

---

## Models

### `CLISession`

A named grouping of commands for one device and user.

| Field        | Type          | Description                              |
|--------------|---------------|------------------------------------------|
| `device`     | FK → Device   | Target device (cascades on delete)       |
| `user`       | FK → User     | Who owns the session                     |
| `name`       | CharField     | Auto-generated name, e.g. `Session #3`  |
| `created_at` | DateTimeField | Auto-set on creation                     |
| `last_used`  | DateTimeField | Updated on every command execution       |

**Property `command_count`** — returns the number of `CLICommand` records linked to this session.

---

### `CLICommand`

One command execution record inside a session.

| Field          | Type          | Description                                   |
|----------------|---------------|-----------------------------------------------|
| `session`      | FK → CLISession | Parent session (cascades on delete)          |
| `command`      | TextField     | Raw command text sent to the device           |
| `output`       | TextField     | Device response text                          |
| `is_error`     | BooleanField  | `True` if the task caught an exception        |
| `executed_at`  | DateTimeField | Auto-set when the record is created           |
| `duration`     | FloatField    | Seconds from send to response                 |

---

## WebSocket Terminal

### `SSHConsumer` (`consumers.py`)

Async Django Channels consumer mounted at `/ws/cli/<pk>/`.

**Connection flow:**

```
WebSocket connect
  │
  ├── Auth check: user must have engineer/admin role → close 4403 if not
  ├── Load Device by pk → close 4404 if not found
  │
  ├── Open Paramiko SSHClient in thread pool
  │       ├── device.get_plaintext_password()
  │       ├── invoke_shell(term='xterm-256color', width=220, height=50)
  │       └── send initial newline to wake prompt
  │
  ├── Spawn background thread: SSH → WebSocket
  │       └── select.select() non-blocking read → send_text to browser
  │
  └── Receive loop (WebSocket → SSH)
          ├── { "type": "input", "data": "..." } → channel.send(data)
          └── { "type": "resize", "cols": N, "rows": M } → channel.resize_pty()

WebSocket disconnect → SSH channel close + thread cleanup
```

**Terminal settings:** `xterm-256color`, 220×50 default size, resizable via resize message.

---

## REST API + Celery

### Endpoints

| Method | URL                                | Auth      | Description                                   |
|--------|------------------------------------|-----------|-----------------------------------------------|
| GET    | `/api/cli/sessions/`               | Login     | List sessions (filterable by `device`)        |
| POST   | `/api/cli/sessions/`               | Login     | Create a named session                        |
| GET    | `/api/cli/sessions/<id>/`          | Login     | Session detail                                |
| DELETE | `/api/cli/sessions/<id>/`          | Login     | Delete session + all its commands             |
| GET    | `/api/cli/sessions/<id>/history/`  | Login     | All commands in a session (ordered by time)   |
| POST   | `/api/cli/execute/`                | Engineer+ | Queue a command, returns `task_id`            |
| GET    | `/api/cli/task/<task_id>/`         | Login     | Poll task state and result                    |

### `POST /api/cli/execute/` body

```json
{
  "device_id":  3,
  "command":    "show ip interface brief",
  "session_id": 7
}
```

Returns immediately with:

```json
{
  "task_id": "abc-123",
  "status":  "queued"
}
```

Poll `GET /api/cli/task/<task_id>/` until `state == "SUCCESS"`:

```json
{
  "state":  "SUCCESS",
  "result": {
    "output":      "Interface   IP-Address ...",
    "duration_ms": 312,
    "command_id":  42
  }
}
```

---

## Celery Task — `execute_cli_command`

Queue: `default`. Defined in `tasks.py`.

Accepts `device_id`, `command`, `session_id`, `user_id`.

**Command routing logic:**

| Command type                                          | Netmiko method       |
|-------------------------------------------------------|----------------------|
| `exit`, `end`, `logout`, `quit`                       | Returns empty output (navigation only) |
| `interface`, `router`, `ip route`, `no`, `vlan`, etc. | `send_config_set()`  |
| All other commands                                    | `send_command()`     |

On completion:
- Creates a `CLICommand` record with output and duration
- Updates `session.last_used`
- Returns `{ output, duration_ms, command_id }`

Auth and timeout exceptions are caught and returned as `is_error=True` records with friendly messages rather than crashing the task.

---

## Views and URL

| URL                          | View      | Auth      | Description                                |
|------------------------------|-----------|-----------|--------------------------------------------|
| `/inventory/<pk>/cli/`       | `console` | Engineer+ | Full-page terminal for device `pk`         |

The view manages session switching via a `?session=<id>` query parameter. If no session exists for the device, a new one is created automatically. All previous sessions for the device are passed to the template for the session switcher.

---

## Frontend (`templates/cli/console.html`)

Built on **xterm.js** loaded from CDN.

**Terminal configuration:**

| Setting         | Value                           |
|-----------------|---------------------------------|
| Font            | JetBrains Mono, 14px            |
| Theme           | Dark (`#0d1117` background)     |
| Scrollback      | 5 000 lines                     |
| Cursor          | Block, blinking                 |
| Bell            | Sound disabled                  |

**UI controls:**

| Control       | Action                                      |
|---------------|---------------------------------------------|
| Clear         | Sends `Ctrl+L` to the SSH channel           |
| Copy          | Copies xterm selection to clipboard         |
| Reconnect     | Closes and reopens the WebSocket            |

**Connection status indicator:** `Connecting…` → `Connected` (green) → `Disconnected` / `Error` (red). Displayed in the top-right of the terminal panel.

**Resize handling:** `ResizeObserver` watches the terminal container; on size change, sends `{ type: "resize", cols, rows }` over the WebSocket so the SSH PTY is updated.

---

## WebSocket Routing (`routing.py`)

```python
websocket_urlpatterns = [
    re_path(r'ws/cli/(?P<pk>\d+)/$', SSHConsumer.as_asgi()),
]
```

Registered in the ASGI application (`asgi.py`) alongside Django's HTTP routing. Requires Django Channels and a channel layer (Redis recommended for production).

---

## Dependencies

| Package          | Used for                                  |
|------------------|-------------------------------------------|
| `channels`       | ASGI, WebSocket routing and consumer base |
| `paramiko`       | SSH in `SSHConsumer` (interactive shell)  |
| `netmiko`        | SSH in the Celery task (command API)      |
| `celery`         | Async task execution                      |

---

## Configuration

| Setting                  | Description                                              |
|--------------------------|----------------------------------------------------------|
| `CHANNEL_LAYERS`         | Must point to a Redis channel layer for WebSocket support|
| `CELERY_BROKER_URL`      | Redis (or other) broker for the task queue               |

The SSH credentials used by both paths come from `device.get_plaintext_password()` and `device.get_netmiko_params()` — set on the Device record in Inventory.

---

## Migrations

| Migration        | Description                                       |
|------------------|---------------------------------------------------|
| `0001_initial.py`| Creates `CLISession` and `CLICommand` tables      |
