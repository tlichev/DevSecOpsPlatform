# Accounts App

Authentication, authorization, and user management for the NetOps Platform. Provides a custom `User` model with role-based access control, an email-based two-factor authentication (2FA) system, and a Celery task for OTP delivery.

---

## Models

### `User` (extends `AbstractUser`)

Custom user model located in [models.py](models.py).

| Field      | Type         | Description                                   |
|------------|--------------|-----------------------------------------------|
| `username` | CharField    | Inherited from `AbstractUser`                 |
| `email`    | EmailField   | Required for 2FA; users without one skip 2FA  |
| `role`     | CharField    | One of `admin`, `engineer`, `readonly`        |
| `avatar`   | ImageField   | Optional profile photo, stored in `avatars/`  |

**Roles**

| Role         | Constant            | Access level                                  |
|--------------|---------------------|-----------------------------------------------|
| Administrator | `ROLE_ADMIN`       | Full access including user management         |
| Network Engineer | `ROLE_ENGINEER` | Read/write access; cannot manage users        |
| Read Only    | `ROLE_READONLY`     | View-only access across all apps              |

**Helper methods**

- `is_admin()` — returns `True` for `admin` role or Django superusers
- `is_engineer()` — returns `True` for `admin`, `engineer`, or superusers
- `get_role_display_badge()` — returns Bootstrap colour name for the role badge (`danger`, `primary`, `secondary`)

---

### `TwoFactorCode`

Stores one-time passwords generated during the two-step login flow.

| Field        | Type          | Description                          |
|--------------|---------------|--------------------------------------|
| `user`       | FK → User     | Cascades on user deletion            |
| `code`       | CharField(6)  | Cryptographically random 6-digit OTP |
| `created_at` | DateTimeField | Set automatically on creation        |
| `expires_at` | DateTimeField | 10 minutes after creation            |
| `used`       | BooleanField  | Marked `True` after successful use   |

**Class method `generate_for(user)`**

Deletes all existing codes for the user, then creates a new one with a fresh 10-minute expiry. Uses `secrets.randbelow(1_000_000)` for cryptographically secure generation.

**Instance method `is_valid()`**

Returns `True` only if the code has not been used and has not expired.

---

## Two-Factor Authentication

### Login flow

```
POST /accounts/login/
  │
  ├── credentials invalid → show error
  │
  ├── user has no email → login() directly → redirect to next
  │
  └── user has email
        │
        ├── TwoFactorCode.generate_for(user)
        ├── store pre_auth_* keys in session
        ├── queue send_otp_email Celery task
        └── redirect to /accounts/verify-otp/

POST /accounts/verify-otp/
  │
  ├── no pre_auth_user_id in session → redirect to login
  ├── rate limited (20/min) → clear session, redirect to login
  ├── attempt > 5 → clear session, redirect to login
  │
  ├── code not found or wrong → decrement attempts counter, show error
  ├── code expired → clear session, redirect to login
  │
  └── code valid
        ├── otp.used = True; delete all codes for user
        ├── login(request, user)
        └── redirect to pre_auth_next
```

### Session keys

The pre-auth state is held in the Django session between the two steps:

| Key                  | Contents                                      |
|----------------------|-----------------------------------------------|
| `pre_auth_user_id`   | PK of the authenticating user                 |
| `pre_auth_backend`   | Auth backend string (preserved for `login()`) |
| `pre_auth_next`      | `?next=` URL to redirect after success        |
| `pre_auth_attempts`  | Running count of failed OTP submissions       |
| `pre_auth_resend_at` | ISO timestamp of last resend (cooldown check) |

All keys are cleared on successful login, lockout, or logout via `_clear_pre_auth()`.

### Security controls

| Control              | Detail                                          |
|----------------------|-------------------------------------------------|
| OTP entropy          | `secrets.randbelow(1_000_000)` — 20-bit entropy |
| OTP lifetime         | 10 minutes                                      |
| Single-use           | Marked `used=True` immediately on success       |
| Invalidation on use  | All codes for the user deleted after login      |
| Attempt lockout      | Session cleared after 5 wrong codes             |
| Resend cooldown      | 60 s server-side; 60 s client-side (localStorage) |
| Login rate limit     | 10 requests/min per IP (`django-ratelimit`)     |
| OTP verify rate limit| 20 requests/min per IP                         |
| Email masking        | Displayed as `t***@gmail.com` on the verify page |

---

## Views and URLs

All URLs are mounted under `/accounts/` with `app_name = 'accounts'`.

| URL                      | View                   | Auth required | Description                         |
|--------------------------|------------------------|---------------|-------------------------------------|
| `login/`                 | `login_view`           | No            | Step 1 of login; starts 2FA flow    |
| `logout/`                | `logout_view`          | No            | Clears session and redirects        |
| `verify-otp/`            | `verify_otp_view`      | No (pre-auth) | Step 2 of login; validates OTP      |
| `resend-otp/`            | `resend_otp_view`      | No (pre-auth) | Regenerates and resends the OTP     |
| `profile/`               | `profile_view`         | Yes           | View and update own profile         |
| `password-change/`       | `password_change_view` | Yes           | Change own password                 |
| `users/`                 | `user_list_view`       | Admin only    | List all users, view role breakdown |

---

## Access Control Decorators

Defined in [decorators.py](decorators.py). Both wrap `@login_required` and redirect unauthorized users to the inventory dashboard.

**`@admin_required`**

Allows only users where `is_admin()` is `True`. All others see an error message and are redirected.

```python
@admin_required
def user_list_view(request):
    ...
```

**`@engineer_required`**

Allows `admin` and `engineer` roles. Read-only users are redirected.

```python
@engineer_required
def some_write_view(request):
    ...
```

Both decorators accept an optional `redirect_url` keyword argument to override the default redirect target.

---

## Celery Task — `send_otp_email`

Defined in [tasks.py](tasks.py).

```
accounts.send_otp_email(user_id, code)
```

- Queued on the `default` queue via `apply_async`
- Renders [templates/emails/otp_code.html](../../templates/emails/otp_code.html) — dark-themed branded HTML email
- Falls back to a plain-text body for mail clients that don't support HTML
- Retries up to 2 times with 5-second exponential backoff on any exception
- Logs a warning and exits cleanly if the user has no email address

**Email template context**

| Variable       | Value                              |
|----------------|------------------------------------|
| `user`         | User instance (name used in greeting) |
| `code`         | The 6-digit OTP string             |
| `platform_url` | `settings.PLATFORM_URL` (fallback: `http://localhost:8000`) |
| `expiry_mins`  | `10`                               |

---

## Templates

| Template                              | Purpose                                        |
|---------------------------------------|------------------------------------------------|
| `templates/accounts/login.html`       | Username/password form (step 1)                |
| `templates/accounts/verify_otp.html`  | OTP entry form (step 2); includes resend button with 60 s countdown |
| `templates/accounts/profile.html`     | Profile update form                            |
| `templates/accounts/change_password.html` | Password change form                       |
| `templates/accounts/users.html`       | Admin user list with role statistics           |
| `templates/emails/otp_code.html`      | HTML email with large monospace code display   |

### OTP verification page features

- 6-digit input with `inputmode="numeric"` and `autocomplete="one-time-code"`
- Auto-submits the form when the 6th digit is typed
- Displays masked email address (`t***@gmail.com`)
- Shows remaining attempts counter; turns amber when ≤ 2 remain
- Resend button disabled for 60 s after use (persisted in `localStorage` across page reloads)

---

## Configuration

| Setting              | Where set         | Purpose                                    |
|----------------------|-------------------|--------------------------------------------|
| `AUTH_USER_MODEL`    | `settings.py`     | Must be set to `'accounts.User'`           |
| `DEFAULT_FROM_EMAIL` | `settings.py`     | Sender address for OTP emails              |
| `PLATFORM_URL`       | `settings.py`     | Base URL injected into the email CTA link  |
| Email backend        | `settings.py`     | Any Django email backend (SMTP, console, etc.) |

---

## Migrations

| Migration                    | Description                              |
|------------------------------|------------------------------------------|
| `0001_initial.py`            | Creates the custom `User` model          |
| `0002_twofactorcode.py`      | Adds `TwoFactorCode` with DB index       |
