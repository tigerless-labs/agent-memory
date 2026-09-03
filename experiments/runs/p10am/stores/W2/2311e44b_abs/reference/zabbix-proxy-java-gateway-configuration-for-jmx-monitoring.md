---
name: zabbix-proxy-java-gateway-configuration-for-jmx-monitoring
abstract: Zabbix Proxy Java Gateway configuration for JMX monitoring
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

To configure Zabbix Proxy to communicate with Zabbix Java Gateway:

1. Update zabbix_proxy.conf:
   - JavaGateway=<IP or hostname of ZJG host>
   - StartJavaPollers=<number of pollers>
   - JavaGatewayPort=<JMX port number>

2. Restart Zabbix proxy after changes
3. Test connectivity using telnet or nc
4. For Docker containers: ensure same network or proper routing
