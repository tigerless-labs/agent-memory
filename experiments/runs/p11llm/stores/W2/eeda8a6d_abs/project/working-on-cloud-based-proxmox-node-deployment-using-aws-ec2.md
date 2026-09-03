---
name: working-on-cloud-based-proxmox-node-deployment-using-aws-ec2
abstract: Working on cloud-based Proxmox node deployment using AWS EC2
type: fact
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

Goal: Deploy Proxmox as cloud-based node(s) that integrate with existing home cluster.

Approach:
- Use AWS EC2 instances as cloud Proxmox nodes
- Automate instance provisioning with Bash + AWS CLI scripts
- Configure networking to allow cluster communication between home and cloud nodes
- Security considerations: VPN or restrictive firewall rules for inter-node traffic

Current focus: Basic EC2 instance automation (security groups, EBS volumes, SSH access)
Next phases: Proxmox-specific configuration, cluster setup, network connectivity
