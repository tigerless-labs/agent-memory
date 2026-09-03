---
name: docker-zabbix-monitoring-setup-jmx-monitoring-via-zabbix-proxy-and-java-gateway
abstract: "Docker + Zabbix monitoring setup: JMX monitoring via Zabbix Proxy and Java Gateway"
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

# Docker + Zabbix Monitoring Architecture

## Components

- **Zabbix Server**: Central monitoring server
- **Zabbix Proxy**: Distributed proxy (containerized)
- **Zabbix Java Gateway**: Enables JMX monitoring
- **Docker Infrastructure**: Target environment with Java applications

## Setup Overview

1. Create Zabbix proxy container with network access to Zabbix server
2. Install Zabbix Java Gateway on same host as proxy
3. Configure proxy to communicate with Java Gateway
4. Configure Zabbix server to use proxy for JMX monitoring
5. Create/link JMX template to monitored hosts
6. Verify connectivity between components

## Key Testing Steps

- Test communication between Zabbix server and proxy
- Test connection from Zabbix Java Gateway to target JMX port (use telnet/nc)
- Verify data collection after proxy restart
