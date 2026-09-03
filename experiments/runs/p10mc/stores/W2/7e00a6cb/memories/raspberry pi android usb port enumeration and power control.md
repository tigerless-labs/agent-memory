---
created: 2026-09-02T23:45:52.632651852Z
updated: 2026-09-02T23:45:52.632651852Z
weight: 1.0
last_accessed: 2026-09-02T23:45:52.632651852Z
access_count: 0
pinned: false
links: []
abstract: Raspberry Pi running Android — USB port enumeration via lsusb, identifying physical ports, powering off individual ports via sysfs at /sys/devices/platform/soc/3c980000.usb/buspower, compatibility varies by model
---

## USB Port Enumeration and Power Control on Raspberry Pi + Android

**User's setup:** Raspberry Pi running Android OS, needs to identify and power off individual USB ports.

### Enumeration — identifying which device is on which port

**Method 1: `lsusb` command**
- Lists all connected USB devices with device number, class, and manufacturer
- Run in terminal to see current connections
- Provides the device number needed for sysfs control

**Method 2: Android Device Manager**
- Access via Settings app → "About phone/tablet" → "Hardware information" or "Device information"
- Shows USB device details in GUI

### Powering off a specific USB port

**Via sysfs:**
```bash
echo 0 > /sys/devices/platform/soc/3c980000.usb/buspower
```
- Example shows power-off for device 3's associated port
- Powers off the port itself, does not physically disconnect the device
- Path may vary depending on Raspberry Pi model and Android implementation

### Important caveats
- **Not all Raspberry Pi models support individual port power-off** — support is hardware/OS dependent
- This cuts power to the port but doesn't physically unplug the device
- May require root permissions or specific permissions in Android