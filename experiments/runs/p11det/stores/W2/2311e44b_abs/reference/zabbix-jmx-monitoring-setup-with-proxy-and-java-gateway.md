---
name: zabbix-jmx-monitoring-setup-with-proxy-and-java-gateway
abstract: Zabbix JMX monitoring setup with Proxy and Java Gateway
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

## Configuration

Add to zabbix_proxy.conf:
- JavaGateway=<IP or hostname of ZJG host>
- StartJavaPollers=<number of pollers>  
- JavaGatewayPort=<JMX port number>

Then restart the proxy.

## JMX Template Items

Monitoring items to create:
- JMX Uptime: key jmx[java.lang:type=Runtime,name=Uptime]
- JMX Heap Memory
- JMX Non-Heap Memory
- JMX Thread Count
- JMX CPU Usage

## Triggers

- High CPU: {jmx[java.lang:type=OperatingSystem,name=ProcessCpuLoad].last()}>0.8
- High Heap Memory Usage
- High Non-Heap Memory Usage
- High Thread Count

## Docker Networking

If Zabbix Proxy and Java Gateway in separate containers: place in same network or configure routing for communication.
