---
name: home-nas-device-for-centralized-backupprioritizing-encryption-and-access-control
abstract: Home NAS device for centralized backup—prioritizing encryption and access control
type: decision
status: active
created: 2026-09-01
updated: 2026-09-01
valid_from: 2026-09-01
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## NAS Project

**Context**: Current setup uses external hard drive for backups. Outgrowing capacity; wants centralized backup for laptop and phone.

**Requirements**:
- Central backup location for multiple devices
- Strong security: AES-256 encryption, access control, 2FA preferred
- Needs to support laptop (Time Machine/Backup software) and phone backup

**Models under consideration** (as of May 29, 2023):
- Synology DiskStation DS218j/DS418j (2-bay and 4-bay)
- QNAP TS-231P, TS-453D
- Western Digital My Cloud EX2 Ultra
- Netgear ReadyNAS
- Asustor AS6404T

**Decision factors**:
- Storage capacity needed
- RAID redundancy (prefers 4-bay for RAID 5/6 options)
- Security features critical
- Budget-conscious but willing to invest in reliability
