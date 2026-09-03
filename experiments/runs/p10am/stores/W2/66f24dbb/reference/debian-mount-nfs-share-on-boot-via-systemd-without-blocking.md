---
name: debian-mount-nfs-share-on-boot-via-systemd-without-blocking
abstract: "Debian: mount NFS share on boot via systemd without blocking"
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

Create systemd mount unit file at `/etc/systemd/system/nfsshare.mount`:

```
[Unit]
Description=NFS mount of 192.168.1.100:/nfsshare

[Mount]
What=192.168.1.100:/nfsshare
Where=/mnt/nfs
Type=nfs
Options=nofail,bg,soft,intr,nfsvers=3,tcp

[Install]
WantedBy=multi-user.target
```

Key options:
- `nofail`: continue booting if NFS mount fails
- `bg`: mount in background, doesn't block boot
- `soft`, `intr`, `nfsvers=3`, `tcp`: NFS-specific robustness options

Alternative approach: use `autofs` package with `/etc/auto.master` configuration for lazy mounting.
