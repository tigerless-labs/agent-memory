---
name: raspberry-pi-android-usb-port-power-control-command
abstract: Raspberry Pi Android USB port power control command
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

To identify and power off individual USB ports on a Raspberry Pi running Android:

1. **List connected USB devices:**
   ```
   lsusb
   ```
   Shows device number, class, and manufacturer for each USB device.

2. **Power off a specific port:**
   ```
   echo 0 > /sys/devices/platform/soc/3c980000.usb/buspower
   ```
   This powers off the USB port without physically disconnecting the device.

3. **Limitations:**
   - Not all Raspberry Pi models support powering off individual USB ports
   - Android Device Manager (Settings > About > Hardware information) can also show USB device details
