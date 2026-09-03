---
name: send-glances-data-to-influxdb-for-grafana-monitoring
abstract: Send Glances data to InfluxDB for Grafana monitoring
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

1. Install Glances on monitored system
2. Install InfluxDB Python library: pip install influxdb
3. Configure InfluxDB plugin in /etc/glances/glances.conf with host, port, user, password, database
4. Start Glances with: glances -w -C /etc/glances/glances.conf (web mode)
5. Query data in InfluxDB: SELECT * FROM glances WHERE client='<hostname>'
6. Set up Grafana dashboard to visualize InfluxDB glances measurement
