---
created: 2026-09-02T23:30:18.194680522Z
updated: 2026-09-02T23:30:18.194680522Z
weight: 1.0
last_accessed: 2026-09-02T23:30:18.194680522Z
access_count: 0
pinned: false
links: []
abstract: Zabbix Proxy configuration for Java Gateway communication — JavaGateway, StartJavaPollers, JavaGatewayPort settings; verify connectivity with telnet/nc between proxy and gateway; handle Docker networking requirements
---

## Zabbix Proxy Configuration for Java Gateway

To configure the Zabbix Proxy to communicate with Zabbix Java Gateway (ZJG):

### Configuration File Changes (zabbix_proxy.conf)

Add or update the following lines:

```
JavaGateway=<IP or hostname of the ZJG host>
StartJavaPollers=<number of pollers>
JavaGatewayPort=<JMX port number>
```

### Verification Steps

1. Test connectivity between Zabbix proxy and Java Gateway using:
   - `telnet <gateway-ip> <port>`
   - `nc <gateway-ip> <port>`

2. For Docker deployments: ensure Zabbix proxy and Java Gateway are:
   - In the same Docker network, OR
   - Have proper routing configured between them

### Implementation Notes
- Restart the Zabbix proxy service after making configuration changes
- Java Gateway must be running on the same host as the proxy (or accessible network location)
- Multiple Java pollers can be configured to handle concurrent JMX monitoring requests