---
name: aws-ec2-instance-deployment-script-with-security-group-and-ebs-volume
abstract: AWS EC2 instance deployment script with security group and EBS volume
type: procedure
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

Bash script using AWS CLI to automate EC2 deployment with the following steps:

1. Fetch latest Amazon Linux 2 AMI ID
2. Get public IP of the machine running the script
3. Create security group with SSH access restricted to the script runner's IP
4. Launch EC2 instance (t2.micro) with key pair authentication
5. Create 100 GB EBS volume in the same availability zone
6. Attach EBS volume as /dev/xvdf to the instance
7. Wait for instance to reach 'running' state before attachment
8. Output the public IP for easy SSH access

Key parameters: instance_type=t2.micro, ebs_volume_size=100GB, device=/dev/xvdf

Dependencies: AWS CLI, jq, curl

Note: EBS volume requires manual formatting and mounting after SSH connection to instance. Security approach: restricts SSH to calling machine's public IP only, not recommended for production without additional security layers (bastion host, VPN).
