---
name: iot-networking-protocol-stacks-hvac-lighting-energy-and-inventory-systems
abstract: "IoT networking protocol stacks: HVAC, lighting, energy, and inventory systems"
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

## IoT Protocol Stack Examples

Learned that IoT systems require multiple protocols at different OSI layers:

### Smart HVAC Systems
- **Physical layer**: Wi-Fi or BLE (for sensors and control units)
- **Network layer**: Zigbee or Z-Wave (mesh networking, reliability, range extension)
- **Application layer**: MQTT (sensor → cloud), HTTP/HTTPS (user interface)

### Smart Lighting Systems
- **Physical layer**: Zigbee (sensors and fixtures)
- **Network layer**: Wi-Fi or BLE (cloud connectivity)
- **Application layer**: MQTT (data transmission and commands), HTTP/HTTPS (UI)

### Smart Energy Management Systems
- Uses Modbus TCP/IP (industrial standard for real-time communication)

### Smart Inventory Management Systems
- Uses RFID (wireless tracking, radio waves)

**Key insight**: Protocol choice depends on data type, transmission distance, power requirements, reliability/security needs, and compatibility with existing systems.
