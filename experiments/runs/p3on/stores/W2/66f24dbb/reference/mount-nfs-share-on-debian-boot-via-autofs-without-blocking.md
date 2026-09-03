---
name: mount-nfs-share-on-debian-boot-via-autofs-without-blocking
abstract: Mount NFS share on Debian boot via autofs without blocking
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

Install autofs: sudo apt-get update && sudo apt-get install autofs

Edit /etc/auto.master and add entry:
/mnt/nfs    192.168.1.100:/nfsshare    auto    nofail,bg,soft,intr,nfsvers=3,tcp

Replace 192.168.1.100:/nfsshare with actual NFS address and /mnt/nfs with mount point.

Mount options:
- nofail: continue booting if NFS fails
- bg: mount in background, non-blocking
- soft: return error instead of hanging on timeout
- intr: interruptible
- nfsvers=3,tcp: NFS version 3 over TCP

Restart: sudo systemctl restart autofs

Verify: mount | grep /mnt/nfs
