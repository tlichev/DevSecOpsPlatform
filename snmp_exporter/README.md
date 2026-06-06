# SNMP Exporter (`snmp_exporter/`)

The SNMP Exporter is a Prometheus exporter that acts as a translation layer between Prometheus's HTTP pull model and the UDP-based SNMP protocol used by network devices.

---

## How It Works

```
Prometheus
  │  GET /snmp?target=192.168.100.1&module=cisco_ios
  ▼
SNMP Exporter :9116
  │  SNMP GET/WALK to 192.168.100.1:161 (UDP)
  ▼
Network Device
  │  SNMP response
  ▼
SNMP Exporter
  │  Translate OID values → Prometheus metrics
  ▼
Prometheus
  │  Stores time series
  ▼
Grafana / Alerts
```

The exporter is **stateless** — every Prometheus scrape triggers a live SNMP query to the target device.

---

## File Structure

```
snmp_exporter/
└── snmp.yml     # Module definitions: which OIDs to walk, how to label them
```

---

## `snmp.yml` — Module Configuration

The file defines named **modules**. Each module specifies:

1. `walk` — list of OID subtrees to traverse
2. `auth` — community string and SNMP version
3. `metrics` — explicit metric definitions with labels and type

### Module: `cisco_ios`

Used for all Cisco IOSv routers and IOSvL2 switches.

#### OID subtrees walked

| OID Subtree | MIB | Description |
|---|---|---|
| `1.3.6.1.2.1.1` | SNMPv2-MIB | System: sysDescr, sysName, sysUpTime |
| `1.3.6.1.2.1.2` | IF-MIB | Interface table (ifTable) |
| `1.3.6.1.2.1.31` | IF-MIB | Extended interface table (ifXTable, 64-bit counters) |
| `1.3.6.1.4.1.9.9.109` | CISCO-PROCESS-MIB | CPU utilization |
| `1.3.6.1.2.1.14` | OSPF-MIB | OSPF neighbor table |

#### Metrics defined

| Metric | OID | Type | Description |
|---|---|---|---|
| `sysUpTime` | 1.3.6.1.2.1.1.3.0 | gauge | Device uptime in hundredths of a second |
| `sysName` | 1.3.6.1.2.1.1.5.0 | DisplayString | Device hostname |
| `ifDescr` | 1.3.6.1.2.1.2.2.1.2 | DisplayString | Interface name per index |
| `ifOperStatus` | 1.3.6.1.2.1.2.2.1.8 | gauge | 1=up, 2=down, 3=testing |
| `ifAdminStatus` | 1.3.6.1.2.1.2.2.1.7 | gauge | 1=up, 2=down |
| `ifInOctets` | 1.3.6.1.2.1.2.2.1.10 | counter | Total bytes received |
| `ifOutOctets` | 1.3.6.1.2.1.2.2.1.16 | counter | Total bytes transmitted |
| `ifInErrors` | 1.3.6.1.2.1.2.2.1.14 | counter | Inbound errors |
| `ifOutErrors` | 1.3.6.1.2.1.2.2.1.20 | counter | Outbound errors |
| `cpmCPUTotal5minRev` | 1.3.6.1.4.1.9.9.109.1.1.1.1.8 | gauge | CPU 5-min average (%) |
| `ospfNbrState` | 1.3.6.1.2.1.14.10.1.6 | gauge | OSPF neighbor state (8=Full) |

#### Label lookups

Interface metrics use `lookups` to attach the human-readable interface name as a label:

```yaml
- name: ifInOctets
  oid: 1.3.6.1.2.1.2.2.1.10
  type: counter
  indexes:
    - labelname: ifIndex
      type: gauge
  lookups:
    - labels: [ifIndex]
      labelname: ifDescr
      oid: 1.3.6.1.2.1.2.2.1.2
      type: DisplayString
```

This makes Prometheus metrics look like:
```
ifInOctets{instance="192.168.100.10",ifIndex="1",ifDescr="GigabitEthernet0/0"} 1234567
```

---

## Authentication

```yaml
auths:
  public_v2c:
    community: public
    version: 2
```

For SNMP v3 authentication, add:

```yaml
auths:
  snmpv3_auth:
    version: 3
    auth_username: snmpv3user
    auth_protocol: SHA
    auth_password: authpassword
    priv_protocol: AES
    priv_password: privpassword
```

Then reference it in the module: `auth: snmpv3_auth`

---

## Testing the Exporter

### Check if a device is responding

```bash
curl "http://localhost:9116/snmp?target=192.168.100.1&module=cisco_ios"
```

Expected: a list of Prometheus metrics in text exposition format.

### Check the exporter's own health

```bash
curl http://localhost:9116/metrics
```

### Common errors

| Error in output | Cause | Fix |
|---|---|---|
| `snmp_error_flag 1` | Device unreachable or wrong community | Check IP, SNMP enabled, firewall |
| `snmp_request_duration_seconds` very high | SNMP timeout | Device overloaded or wrong module |
| Empty metrics | OID not supported on this device | Check device MIB support |

---

## Device Configuration Requirements

For SNMP Exporter to work, each network device must have SNMP enabled:

### Cisco IOS — SNMP v2c (minimum)
```
snmp-server community public RO
snmp-server location DataCenter
snmp-server contact noc@company.local
```

### Cisco IOS — SNMP v3 (recommended)
```
snmp-server group MGMT_GROUP v3 priv
snmp-server user snmpv3user MGMT_GROUP v3 auth sha authpassword priv aes 128 privpassword
snmp-server location DataCenter
snmp-server contact noc@company.local
```

### Verify SNMP is working from the host machine

```bash
snmpwalk -v2c -c public 192.168.100.1 1.3.6.1.2.1.1.5.0
# Expected: SNMPv2-MIB::sysName.0 = STRING: R1
```

---

## Adding a New OID/Metric

1. Find the OID in the MIB browser or Cisco documentation
2. Add a metric definition to `snmp.yml` under `cisco_ios.metrics:`
3. Reload the SNMP Exporter:
   ```bash
   docker compose restart snmp_exporter
   ```
4. Verify: `curl "http://localhost:9116/snmp?target=192.168.100.1&module=cisco_ios" | grep your_metric`
5. Add a PromQL query in Grafana or a new alert rule in `prometheus/rules/`

---

## Network Requirements

The SNMP Exporter container must have layer-3 reachability to `192.168.100.0/24` on **UDP port 161**. In the Docker Compose setup, the `snmp_exporter` service is attached to the `eve_ng` network for this purpose.

On a Linux host with EVE-NG running on a `pnet` bridge:
```yaml
networks:
  eve_ng:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: pnet1
```
