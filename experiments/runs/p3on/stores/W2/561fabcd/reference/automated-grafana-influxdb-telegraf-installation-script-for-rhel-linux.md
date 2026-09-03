---
name: automated-grafana-influxdb-telegraf-installation-script-for-rhel-linux
abstract: "Automated Grafana, InfluxDB, Telegraf installation script for RHEL/Linux"
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

Automated bash script for setting up complete monitoring stack on RHEL 7/8 and Linux distributions.

**Steps covered**:
1. Install and configure InfluxDB (add repo, install, modify config to enable auth)
2. Install and configure Telegraf (add repo, install, configure agent)
3. Install Grafana (add repo, install, enable service)
4. Configure InfluxDB as data source in Grafana

**Default credentials**: admin:admin (should be changed in production).

**Key services**: influxdb, telegraf, grafana-server.

**Default access points**:
- InfluxDB: http://localhost:8086
- Grafana: http://localhost:3000

**Configuration**: InfluxDB config at /etc/influxdb/influxdb.conf (auth-enabled flag). Telegraf config at /etc/telegraf/telegraf.conf (urls pointing to InfluxDB).

**API setup**: Script includes curl command to add InfluxDB datasource to Grafana via REST API.

**Note**: Script examples use Grafana 7.5.5; versions should be updated for current requirements.
