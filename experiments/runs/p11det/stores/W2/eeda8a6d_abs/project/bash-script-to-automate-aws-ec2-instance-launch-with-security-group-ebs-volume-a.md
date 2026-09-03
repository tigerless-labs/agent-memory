---
name: bash-script-to-automate-aws-ec2-instance-launch-with-security-group-ebs-volume-a
abstract: "Bash script to automate AWS EC2 instance launch with security group, EBS volume, and SSH access"
type: procedure
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

Developed a Bash script using AWS CLI to automate spinning up Amazon Linux 2 EC2 instances with:

- Automatic security group creation (ProxmoxSSHAccess) that allows SSH (port 22) only from the user's current public IP
- Public IP detection via ipinfo.io for restrictive SSH rules
- Automatic 100 GB EBS volume creation and attachment to /dev/xvdf
- Instance type: t2.micro (initially, can be parameterized)
- Waits for instance to reach 'running' state before attaching volume
- Outputs the instance's public IP for quick SSH connection

Uses jq for JSON parsing and curl for public IP lookup. Script requires AWS CLI configured with appropriate credentials and an existing EC2 key pair.

Related to larger Proxmox cloud infrastructure automation project.
