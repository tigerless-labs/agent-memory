---
created: 2026-09-02T23:43:04.283259722Z
updated: 2026-09-02T23:43:04.283259722Z
weight: 1.0
last_accessed: 2026-09-02T23:43:04.283259722Z
access_count: 0
pinned: false
links: []
abstract: May 2023 — monitoring stack setup on RHEL 7/8 with Grafana, InfluxDB, Telegraf, and Glances system monitoring
---

## Stack Components

- **InfluxDB**: Time-series database for metrics storage
  - Default port: 8086
  - Config: `/etc/influxdb/influxdb.conf`
  - Web UI: http://localhost:8086 (or remote host:8086)
  - Python library: `pip install influxdb`
  - Default credentials: admin:admin (when configured)

- **Telegraf**: Agent for collecting metrics
  - Config: `/etc/telegraf/telegraf.conf`
  - Sends data to InfluxDB at `http://localhost:8086`
  - Default database: telegraf

- **Grafana**: Visualization dashboard
  - Default port: 3000
  - Default credentials: admin:admin
  - Uses InfluxDB as data source
  - Accesses InfluxDB measurement: `glances`

- **Glances**: Cross-platform system monitoring tool (Python-based)
  - Real-time CPU, memory, disk I/O, network metrics
  - Supports client-server and standalone modes
  - Web-based interface available
  - Can export to InfluxDB via plugin

## Glances to InfluxDB Integration

Configuration in `/etc/glances/glances.conf`:
```
[influxdb]
host = <influxdb_host>
port = <influxdb_port>
user = <influxdb_user>
password = <influxdb_password>
database = <influxdb_database>
```

Start Glances with web server and InfluxDB plugin:
```bash
glances -w -C /etc/glances/glances.conf
```

Query data from InfluxDB:
```sql
SELECT * FROM "glances" WHERE "client"='<glances_client_name>'
```

## RHEL Compatibility
Script should work on RHEL 7 and 8; check official docs for version-specific variations in package names and locations.

## Accessing InfluxDB Web UI
- Navigate to: `http://localhost:8086` (or remote host IP/hostname)
- Requires login with credentials
- Alternative: Use InfluxDB CLI (`influx` command) for more advanced management