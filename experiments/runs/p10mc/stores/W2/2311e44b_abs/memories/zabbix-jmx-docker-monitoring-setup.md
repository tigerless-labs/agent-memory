---
created: 2026-09-02T23:30:35.225615176Z
updated: 2026-09-02T23:30:35.225615176Z
weight: 1.0
last_accessed: 2026-09-02T23:30:35.225615176Z
access_count: 0
pinned: false
links: []
abstract: Complete Zabbix JMX monitoring setup for Docker infrastructure with Zabbix proxy, Java Gateway, Docker networking; seven-step process including proxy container creation, Java Gateway installation, proxy configuration, JMX template creation, host linking, and connectivity testing
---

## Zabbix JMX Monitoring in Docker Infrastructure

### Setup Steps

1. **Create Zabbix Proxy Container**
   - Ensure proxy can communicate with Zabbix server
   - Verify network connectivity

2. **Install Zabbix Java Gateway**
   - Deploy on same host as Zabbix proxy
   - Or on accessible network location

3. **Configure Zabbix Proxy**
   - Update zabbix_proxy.conf with:
     - JavaGateway IP/hostname
     - StartJavaPollers count
     - JavaGatewayPort number
   - Restart proxy service

4. **Create JMX Template**
   - Define items (see zabbix-jmx-template-example for specifics)
   - Create triggers for alerting
   - Store 90 days history, 365 days trends

5. **Link Template to Host**
   - Go to Configuration → Hosts
   - Link the JMX template to monitored host

6. **Test Communication**
   - Test Zabbix server to Zabbix proxy connectivity
   - Test Java Gateway to target JMX port connectivity
   - Use telnet or nc for verification

7. **Verify Data Collection**
   - Restart the Zabbix proxy container
   - Confirm data is being collected from JMX port

### Docker Networking Considerations
- Ensure proxy and gateway are in same Docker network, OR
- Configure proper routing between containers/hosts
- Verify DNS resolution if using hostnames

### Related Memories
- zabbix-proxy-java-gateway-config
- zabbix-jmx-template-example