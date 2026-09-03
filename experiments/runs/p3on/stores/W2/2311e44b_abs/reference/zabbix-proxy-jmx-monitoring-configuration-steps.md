---
name: zabbix-proxy-jmx-monitoring-configuration-steps
abstract: Zabbix Proxy JMX monitoring configuration steps
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

# Zabbix Proxy Configuration for Java Gateway

Configuration file: zabbix_proxy.conf

Required parameters:
- JavaGateway=<IP or hostname of the ZJG host>
- StartJavaPollers=<number of pollers>
- JavaGatewayPort=<JMX port number>

After updating configuration, restart the Zabbix proxy.

Test communication between Zabbix proxy and Java Gateway using telnet or nc command.

When running Zabbix proxy and Java Gateway in different Docker containers, ensure they are in the same network or have proper routing for communication.
