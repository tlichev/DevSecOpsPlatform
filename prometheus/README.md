# Prometheus (`prometheus/`)

Prometheus is the metrics collection and storage engine. It scrapes SNMP metrics from network devices (via SNMP Exporter), host metrics (via Node Exporter), and evaluates alerting rules.

---

## File Structure

```
prometheus/
├── prometheus.yml          # Main Prometheus configuration
├── alertmanager.yml        # AlertManager routing and receiver configuration
└── rules/
    └── network_alerts.yml  # Alerting rules for network devices and host
```

---

## `prometheus.yml` — Main Configuration

### Global settings

```yaml
global:
  scrape_interval: 30s       # How often to scrape targets
  evaluation_interval: 30s   # How often to evaluate alerting rules
  scrape_timeout: 20s        # Per-scrape timeout
```

### Scrape jobs

| Job | Target | Metrics |
|---|---|---|
| `prometheus` | `localhost:9090` | Prometheus self-metrics |
| `node_exporter` | `node_exporter:9100` | Host CPU, memory, disk, network |
| `snmp_cisco` | `192.168.100.x:9116` | Network device SNMP metrics |
| `django` | `django:8000/metrics` | Django app metrics (if enabled) |

### SNMP relabeling

The SNMP job uses relabeling to route each device IP through the SNMP Exporter:

```yaml
- job_name: snmp_cisco
  static_configs:
    - targets:
        - 192.168.100.1   # R1
        - 192.168.100.10  # Core-SW
  metrics_path: /snmp
  params:
    module: [cisco_ios]
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target      # device IP → SNMP target param
    - source_labels: [__param_target]
      target_label: instance            # device IP → instance label
    - target_label: __address__
      replacement: snmp_exporter:9116   # actual scrape goes to SNMP Exporter
```

**Adding a new device to monitoring:**
1. Add its IP to the `targets` list in `prometheus.yml`
2. Reload Prometheus config (no restart needed): `curl -X POST http://localhost:9090/-/reload`

### Adding the device dynamically

For larger environments, replace `static_configs` with file-based service discovery:

```yaml
- job_name: snmp_cisco
  file_sd_configs:
    - files: ['/etc/prometheus/targets/*.yml']
      refresh_interval: 1m
```

Then generate target files from Django inventory via a management command.

---

## `alertmanager.yml` — AlertManager Configuration

### Route tree

```yaml
route:
  group_by: ["alertname", "instance"]
  group_wait: 30s          # Wait before sending first notification in a group
  group_interval: 5m       # Wait between notifications for the same group
  repeat_interval: 4h      # Re-notify if still firing after 4 hours
  receiver: django_webhook
```

All alerts — both `critical` and `warning` — are sent to the Django webhook receiver.

### Receiver

```yaml
receivers:
  - name: django_webhook
    webhook_configs:
      - url: "http://django:8000/api/monitoring/webhook/alertmanager/"
        send_resolved: true    # Also send when alerts resolve
```

`send_resolved: true` is critical — it tells AlertManager to POST a resolved notification when a condition clears. Django updates `Alert.status = "resolved"` on receipt.

### Inhibition rules

Critical alerts suppress (inhibit) warnings for the same instance and alertname:

```yaml
inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["instance", "alertname"]
```

If a critical `InterfaceDown` fires for `192.168.100.1`, any warning-level `HighInterfaceErrorRate` for the same instance is suppressed.

---

## `rules/network_alerts.yml` — Alerting Rules

### Group: `network_device_alerts`

#### InterfaceDown
```yaml
expr: ifOperStatus{job="snmp_cisco"} == 2
for: 2m
severity: critical
```
Fires when `ifOperStatus` equals 2 (down) for 2 minutes. The `for` clause prevents alerting on brief flaps.

#### HighInterfaceErrorRate
```yaml
expr: rate(ifInErrors[5m]) / (rate(ifInOctets[5m]) + 1) > 0.01
for: 5m
severity: warning
```
Fires when inbound errors exceed 1% of inbound traffic over 5 minutes. The `+ 1` prevents division by zero on idle interfaces.

#### SNMPTargetDown
```yaml
expr: up{job="snmp_cisco"} == 0
for: 3m
severity: critical
```
Fires when Prometheus cannot scrape a device via SNMP Exporter. Indicates device unreachability, SNMP misconfiguration, or SNMP Exporter failure.

#### HighCPUUtilization
```yaml
expr: cpmCPUTotal5minRev{job="snmp_cisco"} > 80
for: 5m
severity: warning
```
Uses Cisco's proprietary `cpmCPUTotal5minRev` OID. Only applies to Cisco IOS devices with the `CISCO-PROCESS-MIB`.

#### OSPFNeighborNotFull
```yaml
expr: ospfNbrState{job="snmp_cisco"} != 8
for: 2m
severity: critical
```
OSPF neighbor state 8 = Full (stable adjacency). Any other value means the adjacency is not established.

### Group: `host_alerts`

#### HostHighCPU
```yaml
expr: 100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
for: 5m
```

#### HostDiskSpaceLow
```yaml
expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 10
```

---

## Querying Prometheus

Access the Prometheus UI at `http://localhost:9090`.

### Useful queries

```promql
# All interface states for all SNMP devices
ifOperStatus{job="snmp_cisco"}

# Inbound bandwidth in bytes/sec per interface
rate(ifInOctets{job="snmp_cisco"}[5m])

# Outbound bandwidth in Mbps
rate(ifOutOctets{job="snmp_cisco"}[5m]) * 8 / 1e6

# CPU utilization per Cisco device
cpmCPUTotal5minRev{job="snmp_cisco"}

# OSPF neighbor states
ospfNbrState{job="snmp_cisco"}

# Host CPU usage percentage
100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Host free disk space percentage
(node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100
```

### Reload config without restart

After editing `prometheus.yml` or any rule file:

```bash
curl -X POST http://localhost:9090/-/reload
```

Prometheus has `--web.enable-lifecycle` flag enabled for this purpose.

---

## Data Retention

Configured with `--storage.tsdb.retention.time=30d`. Metrics older than 30 days are automatically deleted. The TSDB storage is in the `prometheus_data` Docker volume.

To change retention:
```yaml
# docker-compose.yml
prometheus:
  command:
    - --storage.tsdb.retention.time=90d   # 90 days
```
