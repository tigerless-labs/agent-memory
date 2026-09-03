---
name: usb-port-control-on-raspberry-pi-running-android
abstract: USB port control on Raspberry Pi running Android
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

Use lsusb to identify devices. Power off ports via sysfs: echo 0 to /sys/devices/platform/soc/3c980000.usb/buspower. Not all RPi models support this.
