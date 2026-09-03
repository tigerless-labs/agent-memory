---
name: zabbix-jmx-template-example-with-items-and-triggers
abstract: Zabbix JMX template example with items and triggers
type: reference
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

# Example JMX Template for Zabbix

## Template Items

1. **JMX Uptime**
   - Type: Zabbix agent
   - Key: jmx[java.lang:type=Runtime,name=Uptime]
   - Update interval: 60s
   - History storage: 90d
   - Trends storage: 365d

2. **JMX Heap Memory**

3. **JMX Non-Heap Memory**

4. **JMX Thread Count**

5. **JMX CPU Usage**

## Triggers

1. **High CPU Usage**
   - Expression: {JMX template:jmx[java.lang:type=OperatingSystem,name=ProcessCpuLoad].last()}>0.8
   - Severity: High

2. **High Heap Memory Usage**

3. **High Non-Heap Memory Usage**

4. **High Thread Count**

## Setup Steps

1. Navigate to Configuration → Templates → Create template
2. Add items in the Items tab
3. Add triggers in the Triggers tab
4. Link template to the host in Configuration → Hosts

Use this template to monitor Java-based services running in containers.
