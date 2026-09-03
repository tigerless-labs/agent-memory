---
name: usb-port-power-control-on-raspberry-pi-running-android-lsusb-identification-and
abstract: USB port power control on Raspberry Pi running Android - lsusb identification and sysfs method
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

Technical reference from 2023: To identify and power off individual USB ports on a Raspberry Pi running Android:

1. **Identify ports**: Use `lsusb` command in terminal to list USB devices with device numbers, classes, and manufacturers
2. **Power off port**: Write to sysfs to disable power: `echo 0 > /sys/devices/platform/soc/3c980000.usb/buspower`
3. **Limitation**: Not all Raspberry Pi models support individual USB port power control

Note: This only powers off the port; physical disconnection requires unplugging the device.
