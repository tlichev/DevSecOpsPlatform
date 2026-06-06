# CI/CD Pipeline (`.github/workflows/`)

The GitHub Actions pipeline implements a complete DevSecOps workflow with security scanning at every stage. It runs on every push to `main` or `develop` and on every pull request targeting `main`.

---

## File Structure

```
.github/
└── workflows/
    ├── devsecops.yml   # Main CI/CD pipeline
    └── README.md       # This file
```

---

## Pipeline Overview

```
Push / PR
    │
    ├─── lint          YAML linting + Ansible playbook linting
    ├─── bandit        Python SAST — finds security anti-patterns in source code
    ├─── pip_audit     Dependency CVE scan — checks requirements.txt against OSV database
    ├─── trivy         Container CVE scan — scans the built Docker image
    └─── test          Django tests with real PostgreSQL + Redis
            │
            └─ (only on push to main, after all above pass)
                    │
                    ├─── build_push    Build Docker image → push to GHCR
                    └─── deploy_staging  SSH deploy to staging server
```

The `build_push` and `deploy_staging` jobs only run when:
- All security jobs (`lint`, `bandit`, `pip_audit`, `test`) pass
- The push is to the `main` branch (not PRs, not `develop`)

---

## Jobs

### `lint` — Code and Config Linting

**Runs:** Always (push and PR)

**Tools:**
- `yamllint` — validates YAML syntax and style in `prometheus/`, `snmp_exporter/`, `grafana/`, `docker-compose.yml`
- `ansible-lint` — validates Ansible playbooks against best-practice rules

**Fail behavior:** Blocks the pipeline if YAML is malformed or Ansible tasks use deprecated syntax.

**yamllint config:** `relaxed` profile (allows some flexibility in line length and quoting).

---

### `bandit` — Static Application Security Testing (SAST)

**Runs:** Always

**What it scans:** All Python source in `apps/` and `devsecops_platform/`

**Severity filter:** `-ll` — reports medium and high severity findings only (skips informational).

**Excludes:** `.git`, `venv`, `staticfiles`

**Output:** `bandit-report.json` — uploaded as a pipeline artifact. Viewable in the GitHub Actions run → Artifacts.

**Fail behavior:** The pipeline continues even if Bandit finds issues (`|| true` in the scan command). The report is uploaded for review. If you want a hard block, remove `|| true`.

**Common Bandit rules checked:**
| Rule ID | What it catches |
|---|---|
| B101 | `assert` statements (stripped in optimized bytecode) |
| B105/B106 | Hardcoded passwords |
| B201 | Flask debug mode (N/A here, but runs anyway) |
| B301/B302 | Pickle deserialization |
| B501-B509 | Insecure SSL/TLS usage |
| B601-B612 | Shell injection in subprocess calls |

---

### `pip_audit` — Dependency Vulnerability Scan

**Runs:** Always

**What it scans:** Every package in `requirements.txt`, checked against the [OSV (Open Source Vulnerabilities)](https://osv.dev) database.

**Output:** `pip-audit-report.json` — uploaded as pipeline artifact.

**Fail behavior:** Non-blocking (`|| true`). Review the artifact for known CVEs in dependencies.

**When a CVE is found:**
1. Check if a patched version exists: `pip-audit -r requirements.txt --fix --dry-run`
2. Update the affected package in `requirements.txt`
3. Re-run the pipeline — the new scan must show zero vulnerabilities

---

### `trivy` — Container Image Vulnerability Scan

**Runs:** Always

**How it works:**
1. Builds the Docker image from the `Dockerfile` in the repo
2. Scans the image layers for CVEs in OS packages and Python packages
3. Outputs in SARIF format → uploaded to GitHub's Security tab

**Severity filter:** `CRITICAL,HIGH` only — ignores medium and low findings.

**Fail behavior:** `exit-code: "0"` — non-blocking. Results appear in the GitHub Security tab → Code scanning → Trivy.

**Viewing results:**
- Go to the GitHub repository → Security tab → Code scanning
- Filter by tool: Trivy

---

### `test` — Django Test Suite

**Runs:** Always (push and PR)

**Services:** The job spins up real PostgreSQL 16 and Redis 7.2 containers as GitHub Actions services — no mocking.

**Environment variables:** 17 env vars are set to match a development environment. All secrets use test-only values (e.g., `ci-test-secret-key-not-for-production`).

**Steps:**
1. Install Python 3.11 and all dependencies from `requirements.txt`
2. Run `python manage.py migrate --noinput`
3. Run `python manage.py seed_compliance_rules`
4. Run `pytest --cov=apps --cov=devsecops_platform --cov-report=xml --cov-report=term-missing -v --tb=short`

**Coverage:** XML coverage report is uploaded as an artifact. Use it with tools like Codecov if desired.

**Fail behavior:** Hard block — if any test fails, the pipeline stops and does not proceed to `build_push`.

---

### `build_push` — Docker Image Build and Push

**Runs:** Only on push to `main`, after all jobs pass.

**Registry:** GitHub Container Registry (GHCR) — `ghcr.io/<owner>/<repo>`

**Authentication:** Uses `GITHUB_TOKEN` (automatically provided by GitHub Actions, no setup needed).

**Tags applied to the image:**
| Tag | Example | When |
|---|---|---|
| Branch name | `main` | Always on branch push |
| Git SHA prefix | `sha-abc1234` | Always |
| `latest` | `latest` | Only when pushing to default branch |

**Build cache:** Uses GitHub Actions cache (`type=gha`) to speed up subsequent builds by reusing unchanged layers.

**Pulling the image:**
```bash
docker pull ghcr.io/<your-username>/devsecopsplatform:latest
```

---

### `deploy_staging` — Staging Deployment

**Runs:** Only on push to `main`, after `build_push` succeeds.

**Environment:** Uses GitHub's `staging` environment — can be configured in repo Settings → Environments with required reviewers and protection rules.

**Required secrets:**
| Secret | Description |
|---|---|
| `STAGING_HOST` | IP or hostname of the staging server |
| `STAGING_USER` | SSH username |
| `STAGING_SSH_KEY` | Private SSH key for the staging user |

**Deployment steps (run on staging server via SSH):**
```bash
cd /opt/devsecops-platform
docker compose pull           # Pull new image
docker compose up -d --remove-orphans  # Restart services
docker compose run --rm django python manage.py migrate --noinput
docker compose run --rm django python manage.py seed_compliance_rules
```

**Setting up secrets:**
1. Generate SSH key pair: `ssh-keygen -t ed25519 -f staging_deploy_key`
2. Add public key to `~/.ssh/authorized_keys` on staging server
3. Add private key as `STAGING_SSH_KEY` secret in GitHub repo → Settings → Secrets

---

## Triggers Summary

| Event | Branches | Jobs that run |
|---|---|---|
| Push | `main` | All 7 jobs |
| Push | `develop` | `lint`, `bandit`, `pip_audit`, `trivy`, `test` |
| Pull Request | targeting `main` | `lint`, `bandit`, `pip_audit`, `trivy`, `test` |

---

## Viewing Pipeline Results

1. Go to your GitHub repository
2. Click the **Actions** tab
3. Select the **DevSecOps CI/CD Pipeline** workflow
4. Click any run to see job logs and artifacts

### Artifacts produced per run

| Artifact | Job | Contents |
|---|---|---|
| `bandit-report` | bandit | JSON SAST findings |
| `pip-audit-report` | pip_audit | JSON dependency CVEs |
| `coverage-report` | test | XML test coverage data |

Trivy results appear in the **Security tab** (not artifacts).

---

## Required GitHub Repository Settings

For the full pipeline to work:

1. **GHCR access**: Default `GITHUB_TOKEN` permissions must include `packages: write`. Enable under repo Settings → Actions → General → Workflow permissions → "Read and write permissions".

2. **Staging environment**: Create a `staging` environment under Settings → Environments. Add `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY` secrets there.

3. **Security tab**: Must be enabled for Trivy SARIF upload. Public repos have this by default; private repos require GitHub Advanced Security.
