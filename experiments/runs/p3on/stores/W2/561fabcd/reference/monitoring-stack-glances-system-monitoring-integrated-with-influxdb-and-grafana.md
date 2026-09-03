---
name: monitoring-stack-glances-system-monitoring-integrated-with-influxdb-and-grafana
abstract: "Monitoring stack: Glances system monitoring integrated with InfluxDB and Grafana"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-20
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Setup explored integrating Glances (system monitoring tool) with InfluxDB (time-series database) and Grafana (visualization dashboard).

**Glances** - Cross-platform system monitoring tool (Python/psutil); provides real-time CPU, memory, disk I/O, network metrics.

**InfluxDB** - Time-series database; web UI at http://localhost:8086.

**Telegraf** - Alternative metric collection agent.

**Configuration**: Install influxdb Python library (pip install influxdb). Edit /etc/glances/glances.conf and add InfluxDB plugin settings. Start with: glances -w -C /etc/glances/glances.conf.

**Access**: InfluxDB web UI at http://localhost:8086 (port 8086 must be open in firewall). Also available via CLI (influx command).

**Compatible with RHEL 7 and 8** plus other Linux distributions.

**Grafana Integration**: Create dashboards using InfluxDB data source, querying the glances measurement.
