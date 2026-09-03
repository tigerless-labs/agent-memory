---
name: ec2-deployment-specifications-t2-micro-amazon-linux-2-with-100-gb-ebs-volume
abstract: "EC2 deployment specifications: t2.micro Amazon Linux 2 with 100 GB EBS volume"
type: decision
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

Infrastructure deployment decision:

**Instance Configuration:**
- Instance type: t2.micro
- AMI: Amazon Linux 2 (latest)
- SSH key pair: (configured per environment)

**Storage:**
- EBS volume: 100 GB
- Device mapping: /dev/xvdf
- Volume type: default (gp2 assumed)

**Networking:**
- Security group: custom per deployment
- SSH access: restricted to calling machine's public IP only
- Port 22: inbound allowed only from script runner's IP

**Rationale:** Automation for cloud-based Proxmox node deployment with isolated SSH access and dedicated high-capacity storage.

**Next steps:** Format and mount EBS volume after instance launch; consider permanent security group if this becomes recurring deployment.
