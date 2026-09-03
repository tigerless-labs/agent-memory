---
created: 2026-09-03T01:27:04.607919361Z
updated: 2026-09-03T01:27:04.607919361Z
weight: 1.0
last_accessed: 2026-09-03T01:27:04.607919361Z
access_count: 0
pinned: false
links: []
abstract: Debian NFS mount on boot without blocking — autofs vs systemd approaches, 192.168.1.100:/nfsshare to /mnt/nfs, nofail/bg/soft/intr/nfsvers=3/tcp options
---

## Mounting NFS on Boot Without Blocking Boot on Debian

User explored two approaches:

### Approach 1: autofs
- Install: `sudo apt-get update && sudo apt-get install autofs`
- Edit `/etc/auto.master` and add entry:
  ```
  /mnt/nfs    192.168.1.100:/nfsshare    auto    nofail,bg,soft,intr,nfsvers=3,tcp
  ```
- Restart: `sudo systemctl restart autofs`
- Key options:
  - `nofail`: continue booting if NFS share fails to mount
  - `bg`: mount in background, don't block boot
  - `soft`: soft timeout (fail faster)
  - `intr`: allow interruption
  - `nfsvers=3,tcp`: NFS version and protocol

### Approach 2: systemd (preferred by user)
- Create `/etc/systemd/system/nfsshare.mount` with:
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
- Same option meanings apply
- Verify with: `mount` command to check `/mnt/nfs` mount point

**Key insight**: The `nofail` option is critical to prevent boot blocking on NFS failure.