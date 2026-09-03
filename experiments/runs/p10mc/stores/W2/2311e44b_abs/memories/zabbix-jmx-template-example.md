---
created: 2026-09-02T23:30:24.510195223Z
updated: 2026-09-02T23:30:24.510195223Z
weight: 1.0
last_accessed: 2026-09-02T23:30:24.510195223Z
access_count: 0
pinned: false
links: []
abstract: Zabbix JMX template example with items (Uptime, Heap Memory, Non-Heap Memory, Thread Count, CPU Usage) and triggers (High CPU >0.8, High Memory, High Thread Count); includes key attribute format jmx[java.lang:type=...,name=...]
---

## Zabbix JMX Template Example

### Template Structure
- Name: "JMX template"
- Items update interval: 60 seconds
- History storage: 90d
- Trends storage: 365d

### Sample Items to Create

1. **JMX Uptime**
   - Type: Zabbix agent
   - Key: `jmx[java.lang:type=Runtime,name=Uptime]`

2. **JMX Heap Memory**
   - Type: Zabbix agent
   - Key: `jmx[java.lang:type=Memory,name=HeapMemoryUsage]`

3. **JMX Non-Heap Memory**
   - Type: Zabbix agent
   - Key: `jmx[java.lang:type=Memory,name=NonHeapMemoryUsage]`

4. **JMX Thread Count**
   - Type: Zabbix agent
   - Key: `jmx[java.lang:type=Threading,name=ThreadCount]`

5. **JMX CPU Usage**
   - Type: Zabbix agent
   - Key: `jmx[java.lang:type=OperatingSystem,name=ProcessCpuLoad]`

### Sample Triggers

1. **High CPU Usage** (Severity: High)
   - Expression: `{JMX template:jmx[java.lang:type=OperatingSystem,name=ProcessCpuLoad].last()}>0.8`

2. **High Heap Memory Usage**
   - Similar pattern using HeapMemoryUsage threshold

3. **High Non-Heap Memory Usage**
   - Similar pattern using NonHeapMemoryUsage threshold

4. **High Thread Count**
   - Similar pattern using ThreadCount threshold

### Setup Steps
1. Go to Configuration → Templates → Create template
2. Add items under "Items" tab
3. Add triggers under "Triggers" tab
4. Link template to hosts under Configuration → Hosts