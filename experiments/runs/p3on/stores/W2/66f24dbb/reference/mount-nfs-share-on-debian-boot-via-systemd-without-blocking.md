---
name: mount-nfs-share-on-debian-boot-via-systemd-without-blocking
abstract: Mount NFS share on Debian boot via systemd without blocking
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Create file /etc/systemd/system/nfsshare.mount:

[Unit]
Description=NFS mount of 192.168.1.100:/nfsshare

[Mount]
What=192.168.1.100:/nfsshare
Where=/mnt/nfs
Type=nfs
Options=nofail,bg,soft,intr,nfsvers=3,tcp

[Install]
WantedBy=multi-user.target

Replace 192.168.1.100:/nfsshare with actual NFS address and /mnt/nfs with mount point.

Mount options:
- nofail: continue booting if NFS mount fails
- bg: mount in background, non-blocking
- soft: return error instead of hanging on timeout
- intr: interruptible
- nfsvers=3,tcp: NFS version 3 over TCP

Enable and start:
sudo systemctl daemon-reload
sudo systemctl enable nfsshare.mount
sudo systemctl start nfsshare.mount

Verify: mount | grep /mnt/nfs
