---
name: zabbix-jmx-template-example-with-monitoring-items-and-triggers
abstract: Zabbix JMX template example with monitoring items and triggers
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

JMX Template for monitoring Java services in Zabbix:

**Items to create (update interval 60s, history 90d, trends 365d):**
- JMX Uptime (key: java.lang:type=Runtime,name=Uptime)
- JMX Heap Memory
- JMX Non-Heap Memory  
- JMX Thread Count
- JMX CPU Usage (key: java.lang:type=OperatingSystem,name=ProcessCpuLoad)

**Triggers to configure:**
- High CPU Usage (threshold >0.8, severity High)
- High Heap Memory Usage
- High Non-Heap Memory Usage
- High Thread Count

**Setup:**
- Create template in Zabbix web interface
- Add items and triggers as listed above
- Link template to hosts via Configuration → Hosts
- Adjust thresholds based on requirements
