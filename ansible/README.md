# Ansible (`ansible/`)

The Ansible directory contains the security hardening baseline for all Cisco IOS network devices in the EVE-NG topology. The playbook applies a consistent set of security controls to every device in the management subnet.

---

## File Structure

```
ansible/
├── inventory.ini          # Static inventory of all EVE-NG devices
└── playbooks/
    └── hardening.yml      # Security hardening baseline playbook
```

---

## Device Inventory — `inventory.ini`

All 5 network devices in the management subnet are defined statically.

| Hostname | IP Address | Role |
|---|---|---|
| R1 | 192.168.100.1 | Core Router |
| FW | 192.168.100.2 | Firewall |
| Core-SW | 192.168.100.10 | Core Switch |
| SW1 | 192.168.100.11 | Access Switch |
| SW2 | 192.168.100.12 | Access Switch |

### Authentication

```ini
[cisco_devices:vars]
ansible_user=admin
ansible_password={{ lookup('env', 'DEVICE_PASSWORD') }}
ansible_network_os=ios
ansible_connection=network_cli
ansible_become=true
ansible_become_method=enable
```

The device password is **never hardcoded** — it is read from the `DEVICE_PASSWORD` environment variable at runtime.

---

## Playbook — `playbooks/hardening.yml`

Applies 7 tasks to every device in the `cisco_devices` group. Runs with `gather_facts: false` because network devices do not support Ansible fact-gathering the same way Linux hosts do.

### Task Breakdown

#### 1. Disable unnecessary services
```yaml
- no service finger          # Disable finger protocol (RFC 742)
- no ip http server          # Disable plaintext HTTP management
- no ip http secure-server   # Disable HTTPS management (use SSH only)
- no cdp run                 # Disable Cisco Discovery Protocol globally
- no ip source-route         # Block source-routed packets (CVE mitigation)
- service password-encryption  # Encrypt all passwords in running-config
- security passwords min-length 10  # Enforce 10-char minimum password length
```

#### 2. Configure SSH v2
```yaml
- ip ssh version 2           # Force SSH v2 (v1 is cryptographically broken)
- ip ssh time-out 60         # Disconnect unauthenticated SSH sessions after 60s
- ip ssh authentication-retries 3  # Lock after 3 failed attempts
```

#### 3. Restrict VTY lines to SSH-only
```yaml
line vty 0 4:
  - transport input ssh      # Block Telnet on all virtual terminal lines
  - login local              # Use local username/password, not just password
  - exec-timeout 10 0        # Disconnect idle sessions after 10 minutes
  - access-class MGMT_ACCESS in  # Apply management ACL
```

#### 4. Configure management ACL
```yaml
ip access-list standard MGMT_ACCESS:
  - permit 192.168.100.0 0.0.0.255  # Allow only management subnet
  - deny any log                     # Log and drop all other sources
```

#### 5. Enable centralized logging
```yaml
- logging buffered 16384     # Buffer 16KB of logs in memory
- logging console critical   # Only critical messages to console
- service timestamps log datetime msec localtime show-timezone
```

#### 6. Configure MOTD banner
```yaml
banner motd # AUTHORIZED ACCESS ONLY - This system is monitored #
```

Required by most compliance frameworks (NIST, CIS) as legal notice before authentication.

#### 7. Save running configuration
```yaml
cisco.ios.ios_command:
  commands:
    - write memory
```

Saves the applied configuration to NVRAM so it survives reboots.

---

## Prerequisites

Install Ansible and the Cisco IOS collection:

```bash
pip install ansible ansible-lint
ansible-galaxy collection install cisco.ios
```

The `cisco.ios` collection provides the `ios_config` and `ios_command` modules used in the playbook. Without it, the playbook will fail immediately.

---

## Running the Playbook

### From the host machine (EVE-NG reachable)

```bash
# Set the device password
export DEVICE_PASSWORD="your_device_password"

# Dry run — check what would change without applying
ansible-playbook -i ansible/inventory.ini ansible/playbooks/hardening.yml --check

# Apply hardening to all devices
ansible-playbook -i ansible/inventory.ini ansible/playbooks/hardening.yml

# Apply to one device only
ansible-playbook -i ansible/inventory.ini ansible/playbooks/hardening.yml --limit R1

# Apply with verbose output (shows all commands sent)
ansible-playbook -i ansible/inventory.ini ansible/playbooks/hardening.yml -v
```

### From the Django container

The Django container has `openssh-client` installed. If Ansible is added to `requirements.txt`, it can be run inside the container:

```bash
docker compose exec django bash
export DEVICE_PASSWORD="your_device_password"
ansible-playbook -i ansible/inventory.ini ansible/playbooks/hardening.yml
```

---

## Relationship to Compliance Checks

The Ansible playbook applies the hardening controls **imperatively** — it pushes configuration to the device.

The Django security app's compliance checks **verify** those same controls are in place by querying the device's running configuration over SSH.

The workflow is:

```
1. Run Ansible playbook → pushes hardening config to all devices
2. Run Django compliance checks → verify every rule is active
3. Any failure in step 2 → use the rule's remediation snippet to fix the gap
4. Take a golden snapshot → baseline for drift detection
```

---

## Adding a New Playbook

1. Create `ansible/playbooks/your_playbook.yml`
2. Use `cisco.ios.ios_config` for configuration changes
3. Use `cisco.ios.ios_command` for read-only show commands
4. Test with `--check` flag first
5. Update this README

### Example — configure NTP

```yaml
- name: Configure NTP
  cisco.ios.ios_config:
    lines:
      - ntp server 192.168.100.254
      - ntp update-calendar
```

---

## Security Notes

- Never commit `ansible_password` in plaintext to version control
- The `DEVICE_PASSWORD` environment variable approach keeps secrets out of git
- For production, use Ansible Vault: `ansible-vault encrypt_string 'password' --name 'ansible_password'`
- SSH keys are preferred over passwords for device authentication in production environments
