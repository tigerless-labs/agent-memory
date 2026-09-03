---
name: aws-ec2-deployment-script-amazon-linux-2-100gb-ebs-ssh-access-public-ip-output
abstract: "AWS EC2 deployment script: Amazon Linux 2, 100GB EBS, SSH access, public IP output"
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

Bash script to spin up AWS EC2 instance with the following configuration:

**Instance Parameters:**
- Instance type: t2.micro
- AMI: Amazon Linux 2 (amzn2-ami-hvm-2.0.????????-x86_64-gp2)
- Security group name: ProxmoxSSHAccess

**EBS Volume:**
- Size: 100 GB
- Device attachment point: /dev/xvdf
- Must be manually formatted and mounted after launch

**Network Security:**
- SSH port 22 restricted to /32 CIDR of the machine running the script
- Public IP obtained via curl https://ipinfo.io/ip
- Uses EC2 key pair (KEY_PAIR_NAME variable)

**Script Workflow:**
Retrieves latest AMI dynamically → detects current machine IP → creates security group → launches instance → creates EBS volume → waits for instance running state → attaches volume → outputs instance public IP

**Requirements:**
AWS CLI with credentials, jq, curl, pre-existing EC2 key pair
