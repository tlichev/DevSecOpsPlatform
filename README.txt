DevSecOps Platform -- Network Infrastructure Automation
========================================================

A production-ready DevSecOps platform for centralized management, monitoring,
provisioning, and security compliance enforcement of Cisco network devices across
a three-site enterprise network emulated in EVE-NG.

Inspired by Cisco DNA Center (DNAC) -- built entirely with open-source tools.


TABLE OF CONTENTS
-----------------
 1.  Concept & Goals
 2.  Network Topology
 3.  IP Addressing
 4.  Firewall High Availability
 5.  Site-to-Site IPSec VPN
 6.  Routing
 7.  System Architecture
 8.  Technology Stack
 9.  Docker Services
10.  Django Applications
11.  Data Flows
12.  API Reference
13.  Security Design
14.  CI/CD Pipeline
15.  Quick Start
16.  Project Structure


===========================================================================
1. CONCEPT & GOALS
===========================================================================

Modern enterprise networks require more than manual CLI work. This platform
provides a single pane of glass for network operations teams:

  Capability        Description
  -----------       -------------------------------------------------------
  Inventory         Central database of all devices, real-time ICMP/SNMP
  CLI Console       Browser-based interactive SSH terminal (xterm.js + WS)
  Provisioning      Push Jinja2 config templates via SSH with before/after diff
  Config Pull       Download full running-config as .txt in one click
  Monitoring        Prometheus + Grafana; AlertManager webhook receiver
  Compliance        12 regex-based security rules vs live running-configs
  Drift Detection   Compare golden baseline vs actual device configs
  RBAC              Admin / Engineer / Read-Only roles on UI and REST API
  2FA               Email OTP, cryptographically secure, 10-minute expiry
  Audit Trail       Every push logged with rendered config, diff, and executor


===========================================================================
2. NETWORK TOPOLOGY
===========================================================================

Three-site enterprise network emulated in EVE-NG (Cisco IOL + ASAv),
connected via Site-to-Site IPSec VPN through a simulated ISP zone.

                    +----------------------------------+
                    |         ISP ZONE (WAN)           |
                    |  SW-Sofia   SW-Plovdiv  SW-Burgas |
                    |  4.2.2.1    4.2.2.33    4.2.2.65  |
                    +------+----------+----------+------+
                           | IPSec    | IPSec    | IPSec
               +-----------+  (full   +-----+    +--------------+
               |              mesh)         |                    |
   +-----------+----------+   +-------------+--------+  +-------+-------------+
   |      SOFIA (HQ)      |   |       PLOVDIV         |  |       BURGAS         |
   |----------------------|   |----------------------|  |----------------------|
   | Sofia-PRIM  4.2.2.2  |   | Plovdiv-PRIM 4.2.2.41|  | Burgas-PRIM 4.2.2.81 |
   | Sofia-SEC   4.2.2.3  |   | Plovdiv-SEC  4.2.2.42|  | Burgas-SEC  4.2.2.82 |
   | VIP         4.2.2.4  |   | VIP          4.2.2.43|  | VIP         4.2.2.83 |
   | LAN  172.16.1.0/29   |   | LAN   172.16.2.0/29  |  | LAN   172.16.3.0/29  |
   | R-Sofia   .1.4       |   | R-Plovdiv    .2.4    |  | R-Burgas    .3.4     |
   | L2S-Sofia            |   | L2S-Plovdiv          |  | L2S-Burgas           |
   +----------------------+   +----------------------+  +----------------------+

15 devices total -- 5 per site:

  Site      Device          Role                        Image
  -------   -----------     -------------------------   ---------------
  Sofia     Sofia-PRIM      Primary Firewall (Active)   Cisco ASAv
  Sofia     Sofia-SEC       Secondary Firewall (Stby)   Cisco ASAv
  Sofia     SW-Sofia        ISP L3 Switch               Cisco IOL L3
  Sofia     L2S-Sofia       LAN L2 Switch               Cisco IOL L2
  Sofia     R-Sofia         Edge Router                 Cisco IOL L3
  Plovdiv   Plovdiv-PRIM    Primary Firewall (Active)   Cisco ASAv
  Plovdiv   Plovdiv-SEC     Secondary Firewall (Stby)   Cisco ASAv
  Plovdiv   SW-Plovdiv      ISP L3 Switch               Cisco IOL L3
  Plovdiv   L2S-Plovdiv     LAN L2 Switch               Cisco IOL L2
  Plovdiv   R-Plovdiv       Edge Router                 Cisco IOL L3
  Burgas    Burgas-PRIM     Primary Firewall (Active)   Cisco ASAv
  Burgas    Burgas-SEC      Secondary Firewall (Stby)   Cisco ASAv
  Burgas    SW-Burgas       ISP L3 Switch               Cisco IOL L3
  Burgas    L2S-Burgas      LAN L2 Switch               Cisco IOL L2
  Burgas    R-Burgas        Edge Router                 Cisco IOL L3


===========================================================================
3. IP ADDRESSING
===========================================================================

WAN (Outside) interfaces -- /27 per site
-----------------------------------------
  Device                  IP          Subnet          Role
  --------------------    ---------   -------------   ----------------------
  SW-Sofia                4.2.2.1     4.2.2.0/27      ISP gateway -- Sofia
  Sofia-PRIM outside      4.2.2.2     4.2.2.0/27      Active firewall WAN
  Sofia-SEC outside       4.2.2.3     4.2.2.0/27      Standby firewall WAN
  Sofia Failover VIP      4.2.2.4     4.2.2.0/27      IPSec tunnel source
  SW-Plovdiv              4.2.2.33    4.2.2.32/27     ISP gateway -- Plovdiv
  Plovdiv-PRIM outside    4.2.2.41    4.2.2.32/27     Active firewall WAN
  Plovdiv-SEC outside     4.2.2.42    4.2.2.32/27     Standby firewall WAN
  Plovdiv Failover VIP    4.2.2.43    4.2.2.32/27     IPSec tunnel source
  SW-Burgas               4.2.2.65    4.2.2.64/27     ISP gateway -- Burgas
  Burgas-PRIM outside     4.2.2.81    4.2.2.64/27     Active firewall WAN
  Burgas-SEC outside      4.2.2.82    4.2.2.64/27     Standby firewall WAN
  Burgas Failover VIP     4.2.2.83    4.2.2.64/27     IPSec tunnel source

LAN (Inside) interfaces -- /29 per site
-----------------------------------------
  Site      Subnet           GW VIP       PRIM IP      SEC IP       Router IP
  -------   ---------------  -----------  -----------  -----------  ----------
  Sofia     172.16.1.0/29    172.16.1.1   172.16.1.2   172.16.1.3   172.16.1.4
  Plovdiv   172.16.2.0/29    172.16.2.1   172.16.2.2   172.16.2.3   172.16.2.4
  Burgas    172.16.3.0/29    172.16.3.1   172.16.3.2   172.16.3.3   172.16.3.4

Failover link addresses
-----------------------------------------
  Site      Failover Link    PRIM        SEC         State Link    PRIM        SEC
  -------   -------------    ---------   ---------   ----------    ---------   ---------
  Sofia     10.0.0.0/30      10.0.0.1    10.0.0.2    10.0.0.4/30   10.0.0.5    10.0.0.6
  Plovdiv   10.0.1.0/30      10.0.1.1    10.0.1.2    10.0.1.4/30   10.0.1.5    10.0.1.6
  Burgas    10.0.2.0/30      10.0.2.1    10.0.2.2    10.0.2.4/30   10.0.2.5    10.0.2.6

Loopback addresses
-----------------------------------------
  Device        Loopback IP       Usage
  ----------    ---------------   ----------------------
  R-Sofia       110.0.0.1/32      Router ID, reachability
  R-Plovdiv     120.0.0.1/32      Router ID, reachability
  R-Burgas      130.0.0.1/32      Router ID, reachability

Management network (planned)
-----------------------------------------
  Device                              Mgmt IP           Interface   Protocol
  ----------------------------------  ----------------  ----------  --------
  Sofia-PRIM                          192.168.1.10      Gi0/3       SSH v2
  Sofia-SEC                           192.168.1.11      Gi0/3       SSH v2
  Plovdiv-PRIM                        192.168.1.20      Gi0/3       SSH v2
  Plovdiv-SEC                         192.168.1.21      Gi0/3       SSH v2
  Burgas-PRIM                         192.168.1.30      Gi0/3       SSH v2
  Burgas-SEC                          192.168.1.31      Gi0/3       SSH v2
  SW-Sofia / SW-Plovdiv / SW-Burgas   192.168.1.40-42   Eth0/3      SSH v2
  R-Sofia / R-Plovdiv / R-Burgas      192.168.1.50-52   Loopback    SSH v2
  Django server                       192.168.1.100     Host        Netmiko


===========================================================================
4. FIREWALL HIGH AVAILABILITY
===========================================================================

Each site has a pair of Cisco ASAv firewalls in Active/Standby mode.
Only the Primary (Active) unit forwards traffic. The Secondary (Standby)
unit synchronises configuration and connection state in real time and takes
over within seconds if Primary fails.

Interface mapping:
  Interface            Role             Connection
  ------------------   ---------------  -----------------------------------------
  GigabitEthernet0/0   outside (WAN)    -> ISP switch
  GigabitEthernet0/1   inside (LAN)     -> L2S switch
  GigabitEthernet0/2   failover link    Direct PRIM <-> SEC (heartbeat + cfg sync)
  GigabitEthernet0/3   management       Planned phase 2
  GigabitEthernet0/4   stateful link    Direct PRIM <-> SEC (conn table sync)
  GigabitEthernet0/5-7 reserved         DMZ, future expansion

Failover behaviour:
  - Heartbeat runs on Gi0/2. Loss of heartbeat -> SEC acquires VIP addresses within seconds
  - Configuration replicates automatically from PRIM to SEC on every change
  - IPSec tunnels always source from the Failover VIP -- tunnel survives failover transparently

ASAv security levels:
  Interface     Security Level   Policy
  -----------   ---------------  ----------------------------
  outside       0                Lowest trust -- internet
  management    50               Medium trust -- management
  inside        100              Full trust -- internal LAN

Outside ACL (inbound from WAN):
  Action   Protocol   Port   Reason
  ------   --------   ----   -------------------
  PERMIT   ESP        --     IPSec payload
  PERMIT   UDP        500    IKEv2 negotiation
  PERMIT   UDP        4500   IKEv2 NAT-T
  DENY     IP         any    Everything else (logged)


===========================================================================
5. SITE-TO-SITE IPSEC VPN
===========================================================================

All three sites are connected in a full mesh of IPSec IKEv2 L2L tunnels.
Each site maintains two tunnels -- one to each of the other sites.
Tunnels always source and terminate on the Failover VIP.

Tunnel matrix:
  Tunnel              Source VIP   Dest VIP     Protected traffic
  ------------------  ----------   ---------    ---------------------------------
  Sofia -> Plovdiv    4.2.2.4      4.2.2.43     172.16.1.0/29 <-> 172.16.2.0/29
  Sofia -> Burgas     4.2.2.4      4.2.2.83     172.16.1.0/29 <-> 172.16.3.0/29
  Plovdiv -> Sofia    4.2.2.43     4.2.2.4      172.16.2.0/29 <-> 172.16.1.0/29
  Plovdiv -> Burgas   4.2.2.43     4.2.2.83     172.16.2.0/29 <-> 172.16.3.0/29
  Burgas -> Sofia     4.2.2.83     4.2.2.4      172.16.3.0/29 <-> 172.16.1.0/29
  Burgas -> Plovdiv   4.2.2.83     4.2.2.43     172.16.3.0/29 <-> 172.16.2.0/29

IKEv2 parameters:
  Parameter          Value
  ----------------   ---------------------------
  IKE version        IKEv2
  Encryption         AES-256
  Integrity          SHA-256
  DH group           Group 14 (2048-bit)
  PRF                SHA-256
  IKE lifetime       86400 s (24 h)
  ESP encryption     AES-256
  ESP integrity      SHA-256
  Authentication     Pre-shared key
  Tunnel type        IPSec L2L (crypto map)

NAT policy:
  - NAT rule 1 -- LAN-A <-> LAN-B (identity NAT, no translation)
  - NAT rule 2 -- LAN-A <-> LAN-C (identity NAT, no translation)
  - NAT after-auto -- LAN -> Internet (dynamic PAT to outside interface)


===========================================================================
6. ROUTING
===========================================================================

All routing is static. Firewalls know the remote LAN subnets and point them
at the IPSec peer VIP. Edge routers have a single default route pointing at
the inside firewall VIP.

Firewall static routes:
  Firewall        Destination       Next Hop     Description
  ------------    ---------------   ----------   ------------------------
  Sofia-PRIM      0.0.0.0/0         4.2.2.1      Default -> ISP
  Sofia-PRIM      172.16.2.0/29     4.2.2.43     Plovdiv LAN via IPSec
  Sofia-PRIM      172.16.3.0/29     4.2.2.83     Burgas LAN via IPSec
  Plovdiv-PRIM    0.0.0.0/0         4.2.2.33     Default -> ISP
  Plovdiv-PRIM    172.16.1.0/29     4.2.2.4      Sofia LAN via IPSec
  Plovdiv-PRIM    172.16.3.0/29     4.2.2.83     Burgas LAN via IPSec
  Burgas-PRIM     0.0.0.0/0         4.2.2.65     Default -> ISP
  Burgas-PRIM     172.16.1.0/29     4.2.2.4      Sofia LAN via IPSec
  Burgas-PRIM     172.16.2.0/29     4.2.2.43     Plovdiv LAN via IPSec

Edge router static routes:
  Router        Destination   Next Hop
  ----------    -----------   ----------------------------
  R-Sofia       0.0.0.0/0     172.16.1.1 (firewall VIP)
  R-Plovdiv     0.0.0.0/0     172.16.2.1 (firewall VIP)
  R-Burgas      0.0.0.0/0     172.16.3.1 (firewall VIP)


===========================================================================
7. SYSTEM ARCHITECTURE
===========================================================================

+--------------------------------------------------------------------+
|                       Docker Compose Stack                          |
|                                                                     |
|  +----------+    +--------------+    +------------------------+    |
|  | Browser  |--->|    Django    |--->|        SQLite          |    |
|  | (xterm.js|    |  (Gunicorn)  |    |      (WAL mode)        |    |
|  |  WS/HTTP)|    |   port 8000  |    +------------------------+    |
|  +----------+    +------+-------+                                   |
|         |  WebSocket    |                                           |
|         |  /ws/cli/<pk> |                                           |
|  +------+------+        |                                           |
|  | Django      |   +----+------------------------+                 |
|  | Channels    |   |  Celery Workers              |                 |
|  | (ASGI)      |   |  queues: provisioning        |                 |
|  +------+------+   |          monitoring          |                 |
|         |          |          discovery           |                 |
|   Paramiko SSH     |          default             |                 |
|         |          +------------+----------------+                  |
|         |               +-------+------+                           |
|         |               |    Redis     |                           |
|         |               |  broker +    |                           |
|         |               |  cache +     |                           |
|         |               |  task results|                           |
|         |               +--------------+                           |
|         |                                                           |
|   +-----+-------------------------------------------+              |
|   |          Observability Stack                      |             |
|   |  Prometheus:9090  Grafana:3000                   |             |
|   |  AlertManager:9093  SNMP Exporter:9116           |             |
|   |  Node Exporter:9100                              |             |
|   +--------------------------------------------------+              |
+-------------------------------+------------------------------------+
                                | SSH + SNMP
             +------------------+------------------+
             |        EVE-NG Network (3 sites)      |
             |  Sofia       Plovdiv       Burgas     |
             |  172.16.1.0  172.16.2.0   172.16.3.0 |
             |  /29         /29          /29         |
             +--------------------------------------+

Config push flow:
  1. Engineer submits push request via UI
  2. Django validates and enqueues a Celery task on 'provisioning' queue
  3. Worker SSHes to device via Netmiko -> captures show running-config (before)
  4. Sends rendered config lines via send_config_set() -> save_config()
  5. Captures show running-config (after) -> computes unified diff
  6. Stores diff + status in AuditLog; browser polls task status every 2 s


===========================================================================
8. TECHNOLOGY STACK
===========================================================================

Backend:
  Component              Technology                           Version
  --------------------   ----------------------------------   -------
  Web framework          Django                               4.2
  REST API               Django REST Framework                3.15
  WebSocket              Django Channels (ASGI)               4.x
  Authentication         Session (UI) + JWT (API)             --
  2FA                    Email OTP via Celery task            --
  Task queue             Celery                               5.3
  Message broker         Redis                                7
  Database               SQLite (WAL mode)                    built-in
  SSH automation         Netmiko (tasks) + Paramiko (WS)      --
  SNMP                   puresnmp                             2.0
  Config templating      Jinja2                               3.1
  Password encryption    Fernet (cryptography)                42.x
  API docs               drf-spectacular (OpenAPI 3)          0.27
  Static files           WhiteNoise                           6.6

Frontend:
  Component              Technology
  --------------------   ----------------------------------------
  UI framework           Bootstrap 5 (dark theme)
  Icons                  Bootstrap Icons
  Fonts                  Inter (UI), JetBrains Mono (terminal)
  Terminal emulator      xterm.js (WebSocket -> Paramiko SSH)
  Topology map           Custom SVG + JavaScript
  Charts                 Embedded Grafana iframes

Observability:
  Component              Technology          Port
  --------------------   -----------------   ----
  Metrics collection     Prometheus          9090
  Device SNMP metrics    SNMP Exporter       9116
  Host metrics           Node Exporter       9100
  Dashboards             Grafana 10          3000
  Alert routing          AlertManager        9093

DevSecOps pipeline:
  Stage                  Tool
  --------------------   ----------------
  Style lint             flake8
  SAST                   Bandit
  Dependency CVEs        pip-audit
  Unit tests             Django TestCase + coverage
  Container scan         Trivy
  CI/CD                  GitHub Actions


===========================================================================
9. DOCKER SERVICES
===========================================================================

9 containers total:

  Service          Port    Role
  ---------------  ------  ---------------------------------------------------
  django           8000    Web UI + REST API + WebSocket (Gunicorn + Daphne)
  celery           --      Async task workers (4 queues)
  celery-beat      --      Periodic task scheduler
  redis            6379    Celery broker + result backend + Django cache
  prometheus       9090    Metrics scraper (30-day retention)
  snmp_exporter    9116    Translates SNMP -> Prometheus metrics
  node_exporter    9100    Host OS metrics
  grafana          3000    Dashboard UI
  alertmanager     9093    Routes Prometheus alerts -> Django webhook

Celery task queues:
  Queue          App                 Tasks
  -----------    -----------------   ------------------------------------------
  discovery      Inventory           ICMP polling, SNMP discovery, device status
  provisioning   Provisioning        SSH config push, running-config pull
  monitoring     Monitoring          Alert sync, device-down reconciliation
  default        Accounts, Security  OTP email, compliance checks, drift

Periodic tasks (Celery Beat):
  Task                      Schedule        Purpose
  -----------------------   -------------   ------------------------------------
  poll-all-devices          Every 5 min     ICMP + SNMP poll all devices
  sync-prometheus-alerts    Every 2 min     Reconcile alerts from Prometheus API
  mark-devices-from-alerts  Every 3 min     Sync device status from active alerts
  daily-compliance-check    02:00           Run all compliance rules on all UP
  daily-drift-check         03:00           Golden config drift on all UP devices


===========================================================================
10. DJANGO APPLICATIONS
===========================================================================

--- apps/accounts --- Authentication, 2FA & RBAC ---

  Full README: apps/accounts/README.md

  Models:
    - User: AbstractUser + role field + avatar
    - TwoFactorCode: 6-digit OTP, 10-minute expiry

  Roles:
    admin     Full access including user management
    engineer  Read/write devices, push configs, run checks
    readonly  View-only across all apps

  Two-factor authentication flow:
    1. User submits username + password -> credentials validated
    2. Users with no email skip 2FA and log in directly
    3. Users with email -> 6-digit OTP via secrets.randbelow(), emailed via Celery
    4. Pre-auth state stored in session (pre_auth_user_id, pre_auth_backend)
    5. User enters code at /accounts/verify-otp/ -> login() called -> redirect

  Security controls:
    - 5-attempt lockout
    - 60 s resend cooldown (server + client)
    - 20 req/min rate limit on OTP verification
    - Email displayed as t***@gmail.com (masked)

  Decorators: @admin_required, @engineer_required for view-level RBAC


--- apps/inventory --- Device Inventory & Discovery ---

  Full README: apps/inventory/README.md

  Model: Device -- all 15 EVE-NG devices registered here with management IPs,
  site, device type, SNMP community, and Fernet-encrypted SSH credentials.

  SSH credential security:
    - Fernet AES encryption at rest
    - Key from FIELD_ENCRYPTION_KEY env var (SHA-256 fallback from SECRET_KEY)
    - Decrypted only inside Celery workers at SSH connection time
    - Never returned by the API (write_only serializer field)

  Celery tasks:
    - poll_device(id):      ICMP ping -> mark_seen() or mark_down()
    - poll_all_devices():   Parallel Celery group for all devices
    - discover_network():   Scans MGMT_NETWORK CIDR, creates Device records
                            for unknown live hosts via SNMP sysName

  REST API: DeviceViewSet with actions poll, poll_all, discover, status_list,
  by_site. Standalone dashboard_stats endpoint feeds dashboard counters.


--- apps/provisioning --- Config Push, File Templates & Config Pull ---

  Full README: apps/provisioning/README.md

  Models:
    - ProvisioningTemplate: DB-stored Jinja2 templates
    - AuditLog: immutable push + pull history

  Template engine: Dual-loader Jinja2 -- DB templates take priority over file
  templates. 9 built-in .j2 files in config_templates/:

    ssh_hardening.j2          SSH v2, disable Telnet/HTTP, AAA, password policy
    ospf_area0.j2             OSPF process, area 0, passive interfaces
    router_ospf_loopback.j2   Loopback + OSPF redistribute connected
    firewall_primary_wan.j2   WAN ACL and NAT rules for ASAv
    ntp_syslog.j2             NTP server, timezone, syslog destination
    snmp_v2c.j2               SNMPv2c community, location, contact, trap host
    acl_management.j2         Management ACL (permit 192.168.1.0/24 only)
    interface_descriptions.j2 Interface descriptions per device type
    vlan_access.j2            Access-port VLAN + spanning-tree portfast

  File template management UI (/provisioning/file-templates/):
    - Create / edit / delete .j2 files via a browser editor
    - Jinja2 syntax validated before saving -- rejected with exact error line
    - Variable chip sidebar inserts {{ variable }} at cursor
    - Filenames validated against ^[a-z0-9_-]+$ -- no path traversal possible

  Config push flow:
    POST /api/provisioning/push/ { device_ids, template_name, dry_run }
      -> Celery: push_config_to_device
           -> Render Jinja2 template
           -> Netmiko SSH -> show running-config (before)
           -> send_config_set() -> save_config()
           -> show running-config (after)
           -> unified_diff(before, after) -> AuditLog
           -> Browser polls /api/provisioning/task/<id>/ every 2 s

  Running-config pull + download:
    [Pull Config] button -> POST /api/provisioning/pull-config/
      -> Celery: pull_running_config
           -> Netmiko SSH -> show running-config -> AuditLog
      Browser polls -> state=SUCCESS
      -> GET /provisioning/pull-config/<task_id>/download/
      -> sofia_sofia-prim_running-config_2026-06-17_23-47.txt


--- apps/cli --- Browser SSH Terminal ---

  Full README: apps/cli/README.md

  Two parallel interfaces:
    WebSocket terminal   Django Channels + Paramiko   Interactive shell, full PTY
    REST + Celery        Netmiko task                 Scripted execution with history

  WebSocket terminal at /inventory/<pk>/cli/:
    - xterm.js with JetBrains Mono, dark theme, 5000-line scrollback
    - SSHConsumer opens Paramiko invoke_shell() PTY (xterm-256color, 220x50)
    - Bidirectional proxy: keyboard -> WebSocket -> SSH; SSH -> WebSocket -> terminal
    - Terminal resize events -> channel.resize_pty()
    - Engineer role required; WebSocket closed 4403 if unauthorized

  REST command API at /api/cli/execute/:
    - Config-mode commands use send_config_set(), exec-mode use send_command()
    - Every command saved as CLICommand record with output, duration, error flag
    - Session history at /api/cli/sessions/<id>/history/


--- apps/monitoring --- Alerts & Dashboards ---

  Full README: apps/monitoring/README.md

  Models:
    - Alert: deduplicated by fingerprint
    - AlertNotification: email delivery log

  AlertManager webhook at POST /api/alerts/webhook/ (no auth, network-isolated):
    - update_or_create(fingerprint=...) -- repeat alerts update existing record
    - DeviceDown alerts instantly set device.status = 'down' in inventory
    - Inhibition rules suppress InterfaceDown / HighInterfaceErrors when device down

  8 Prometheus alert rules:
    DeviceDown, InterfaceDown, HighCPULoad, HighMemoryUsage,
    HighInterfaceErrors, BGPPeerDown, OSPFNeighborLost, SNMPUnreachable

  Email notifications: Celery task send_alert_email on critical alerts


--- apps/security --- Compliance & Drift Detection ---

  Models: ComplianceRule, ComplianceResult, GoldenConfig, DriftResult

  12 built-in compliance rules:
    Rule                         Severity   Check type
    --------------------------   --------   ----------
    SSH v2 enabled               Critical   Presence
    Telnet disabled              Critical   Absence
    AAA new-model                Critical   Presence
    No enable password           Critical   Absence
    NTP server configured        Warning    Presence
    SNMP community with ACL      Warning    Presence
    Syslog host configured       Warning    Presence
    Service password-encryption  Warning    Presence
    OSPF MD5 authentication      Warning    Presence (routers only)
    CDP disabled on firewalls    Warning    Absence (firewalls only)
    Login banner present         Info       Presence
    Service timestamps log       Info       Presence

  Compliance score: (pass_count / applicable_rules) x 100. Compliant >= 80%.

  Drift detection: show running-config via SSH -> difflib.unified_diff(golden, actual)
  -> count +/- lines -> DriftResult. Displayed with green/red/blue syntax colouring.


===========================================================================
11. DATA FLOWS
===========================================================================

SNMP polling loop:
  Celery Beat (every 5 min)
    -> poll_all_devices()
         -> poll_device(id) [discovery queue, parallel group]
               -> ICMP ping
               -> success: device.mark_seen() -> status=up
               -> failure: device.mark_down() -> status=down

Prometheus alert pipeline:
  Device unreachable
    -> Prometheus fires alert rule (rules/alerts.yml)
         -> AlertManager routes + inhibits
               -> POST /api/alerts/webhook/
                     -> Alert.update_or_create(fingerprint=...)
                     -> DeviceDown? -> Device.update(status='down')
                     -> send_alert_email.delay() [critical alerts]

2FA login flow:
  POST /accounts/login/
    -> authenticate() -> user found, has email
    -> TwoFactorCode.generate_for(user) [cryptographically secure]
    -> send_otp_email.apply_async() [default queue]
    -> session['pre_auth_user_id'] = user.pk
    -> redirect -> /accounts/verify-otp/
         -> POST code -> otp.is_valid() -> login() -> redirect(next)

Running-config download:
  [Pull Config] button
    -> POST /api/provisioning/pull-config/ { device_id }
         -> pull_running_config.apply_async() [provisioning queue]
               -> Netmiko SSH -> show running-config -> AuditLog
    Browser polls /api/provisioning/task/<id>/ every 2 s
    -> SUCCESS -> GET /provisioning/pull-config/<task_id>/download/
    -> sofia_r-sofia_running-config_2026-06-17_23-47.txt


===========================================================================
12. API REFERENCE
===========================================================================

Base URL:  http://localhost:8000/api/
API docs:  http://localhost:8000/api/docs/  (Swagger UI)

Authentication:
  POST /api/token/          -> { access, refresh }  (JWT, role in claims)
  POST /api/token/refresh/  -> { access }
  POST /api/token/verify/   -> 200 OK if valid

Inventory:
  GET    /api/devices/                     List (filter: site, status, device_type)
  POST   /api/devices/                     Create (engineer+)
  GET    /api/devices/{id}/                Detail
  PATCH  /api/devices/{id}/                Update (engineer+)
  DELETE /api/devices/{id}/                Delete (admin)
  POST   /api/devices/{id}/poll/           Trigger ICMP poll
  POST   /api/devices/poll_all/            Poll all devices
  POST   /api/devices/discover/            Network discovery scan
  GET    /api/devices/status_list/         Minimal list for topology.js
  GET    /api/devices/by_site/?site=sofia  Filter by site
  GET    /api/inventory/dashboard-stats/   Dashboard counters

Provisioning:
  GET    /api/provisioning/templates/          List DB templates
  POST   /api/provisioning/templates/          Create (engineer+)
  POST   /api/provisioning/render/             Preview render (no SSH)
  POST   /api/provisioning/push/               Push config to device(s)
  POST   /api/provisioning/pull-config/        Pull running-config
  GET    /api/provisioning/task/{task_id}/     Poll task state + result
  GET    /api/provisioning/audit/              Audit log
  GET    /api/provisioning/audit/{id}/         Audit entry detail

CLI:
  GET    /api/cli/sessions/                    List sessions (filter by device)
  POST   /api/cli/sessions/                    Create session
  GET    /api/cli/sessions/{id}/history/       Command history
  POST   /api/cli/execute/                     Run command (async)
  GET    /api/cli/task/{task_id}/              Poll command result
  WS     /ws/cli/{device_pk}/                  Live SSH terminal

Monitoring:
  POST /api/alerts/webhook/                        AlertManager receiver (no auth)
  GET  /api/monitoring/alerts/                     List alerts
  POST /api/monitoring/alerts/{id}/acknowledge/    Acknowledge alert
  GET  /api/monitoring/alerts/active-summary/      Count by severity

Security:
  GET  /api/security/rules/                        Compliance rules
  GET  /api/security/results/                      Compliance results
  GET  /api/security/compliance/summary/           Per-device scores
  POST /api/security/compliance/run/{device_id}/   Run checks on one device
  POST /api/security/compliance/run-all/           Run checks on all UP devices
  POST /api/security/drift/run/{device_id}/        Drift check
  GET  /api/security/golden/                       Golden config baselines
  GET  /api/security/drift/                        Drift results


===========================================================================
13. SECURITY DESIGN
===========================================================================

Authentication layers:
  Layer      Method                              TTL
  --------   ---------------------------------   ---------------------------
  Web UI     Django sessions                     8 hours
  REST API   JWT (SimpleJWT)                     Access: 8 h / Refresh: 7 d
  2FA        Email OTP (secrets.randbelow)       10 minutes

Credential protection:
  - SSH passwords are Fernet-encrypted at rest -- never stored in plaintext
  - Encryption key in FIELD_ENCRYPTION_KEY env var; SHA-256 fallback from SECRET_KEY
  - REST API marks ssh_password as write_only -- never returned in responses
  - OTP codes generated with secrets.randbelow(1_000_000) -- CSPRNG

Rate limiting:
  - Login:            10 POST/min per IP (django-ratelimit -> Redis)
  - OTP verification: 20 POST/min per IP
  - OTP lockout:      5 failed attempts clears session, forces re-login
  - OTP resend:       60-second server-side cooldown (+ client-side via localStorage)

Network security (ASAv):
  - Outside ACL: permit only ESP + UDP/500 + UDP/4500; deny+log everything else
  - Inter-site traffic: identity NAT (no address translation)
  - IPSec: AES-256 / SHA-256 / Group 14 -- no legacy algorithms

HTTP security headers (production):
  Header                       Value
  --------------------------   -----------------------------------------------
  Strict-Transport-Security    max-age=31536000; includeSubDomains; preload
  Content-Security-Policy      default-src 'self'; frame-src 'self' <grafana>
  X-Frame-Options              SAMEORIGIN
  Referrer-Policy              strict-origin-when-cross-origin
  X-Content-Type-Options       nosniff





===========================================================================
15. QUICK START
===========================================================================

  # 1. Clone
  git clone <repo-url> && cd DevSecOpsPlatform

  # 2. Configure environment
  cp .env.example .env

  # Generate SECRET_KEY:
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

  # Generate FIELD_ENCRYPTION_KEY:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

  # Set EMAIL_HOST / EMAIL_PORT / DEFAULT_FROM_EMAIL for 2FA OTP delivery
  # Paste all values into .env

  # 3. Start the stack
  docker compose up -d --build

  # 4. Create admin user
  docker compose exec django python manage.py createsuperuser

  # 5. Open http://localhost:8000
  # Login -> 2FA OTP sent to admin email -> enter code -> dashboard

Production deployment: set DJANGO_SETTINGS_MODULE=config.settings.prod,
configure HTTPS, point PLATFORM_URL to your domain for correct OTP email links.


===========================================================================
16. PROJECT STRUCTURE
===========================================================================

DevSecOpsPlatform/
|-- apps/
|   |-- accounts/               Auth, 2FA, RBAC, user management
|   |   `-- README.md
|   |-- inventory/              Device inventory, ICMP/SNMP polling, discovery
|   |   `-- README.md
|   |-- provisioning/           Config templates, SSH push, config pull, audit
|   |   |-- config_templates/   9 built-in .j2 templates
|   |   `-- README.md
|   |-- cli/                    WebSocket SSH terminal + REST command API
|   |   `-- README.md
|   |-- monitoring/             Alerts, AlertManager webhook, Grafana
|   |   `-- README.md
|   `-- security/               Compliance rules, golden config drift
|-- api/
|   `-- urls.py                 Central DRF router -- all /api/* endpoints
|-- config/
|   |-- settings/
|   |   |-- base.py             Shared settings
|   |   |-- dev.py              Development overrides
|   |   |-- prod.py             Production hardening (HTTPS, CSP, HSTS)
|   |   `-- test.py             CI test settings (in-memory SQLite, no Redis)
|   |-- celery.py               Celery app + autodiscovery
|   `-- asgi.py                 ASGI routing (HTTP + WebSocket)
|-- templates/                  Django HTML templates (Bootstrap 5 dark theme)
|   |-- base.html               Sidebar, topbar, flash messages
|   |-- accounts/               Login, verify-otp, profile, users
|   |-- inventory/              Dashboard, device list/detail/form
|   |-- provisioning/           Home, push, audit, file template editor
|   |-- cli/                    xterm.js console
|   |-- monitoring/             Alert list, dashboards
|   `-- emails/                 OTP email (HTML + text)
|-- static/
|   |-- css/main.css            Dark theme CSS variables
|   `-- js/topology.js          Animated SVG network topology map
|-- fixtures/
|   |-- devices.json            15 EVE-NG devices
|   `-- compliance_rules.json   12 security rules
|-- prometheus/
|   |-- prometheus.yml          Scrape config (SNMP targets)
|   |-- alertmanager.yml        Routing + inhibition rules
|   `-- rules/alerts.yml        8 alert rule definitions
|-- grafana/
|   |-- dashboards/             Provisioned network overview dashboard
|   `-- datasources/            Prometheus datasource config
|-- snmp_exporter/
|   `-- snmp.yml                SNMP OID mappings for Cisco IOS
|-- .github/workflows/
|   `-- devsecops.yml           CI/CD: lint -> SAST -> audit -> test -> Trivy
|-- Dockerfile                  python:3.11-slim, non-root appuser
|-- docker-compose.yml          9-service stack
|-- entrypoint.sh               migrate + collectstatic + loaddata on startup
|-- requirements.txt            All Python dependencies pinned
|-- pyproject.toml              Bandit + coverage config
`-- .env.example                Environment variable template
