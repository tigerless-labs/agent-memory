---
name: iot-protocol-stack-patterns-for-smart-systems-by-application-type
abstract: IoT protocol stack patterns for smart systems by application type
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

**Smart HVAC Systems:**
- Physical layer: Wi-Fi or BLE
- Network layer: Zigbee or Z-Wave (mesh networking)
- Application layer: MQTT, HTTP/HTTPS for cloud platform and UI

**Smart Lighting Systems:**
- Physical layer: Zigbee for occupancy and light sensors
- Network layer: Wi-Fi or BLE to cloud platform
- Application layer: MQTT for data transmission and control commands, HTTP/HTTPS for UI

**Smart Energy Management Systems:**
- Uses Modbus TCP/IP for collecting data from energy meters
- Suitable for industrial/real-time communication

**Smart Inventory Management Systems:**
- Uses RFID for wireless tracking at distance with large data storage
