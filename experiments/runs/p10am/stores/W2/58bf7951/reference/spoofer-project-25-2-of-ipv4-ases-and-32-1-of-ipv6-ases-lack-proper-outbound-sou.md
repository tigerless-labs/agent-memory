---
name: spoofer-project-25-2-of-ipv4-ases-and-32-1-of-ipv6-ases-lack-proper-outbound-sou
abstract: "Spoofer Project: 25.2% of IPv4 ASes and 32.1% of IPv6 ASes lack proper outbound source address validation (August 2019 data)"
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

Year ending August 2019 study of source address validation (SAV) deployment.

Outbound SAV gaps: 25.2% IPv4 ASes, 32.1% IPv6 ASes lack deployment. Excluding NAT: 14.9% IPv4 /24 prefixes, 12.3% IPv6 /40 prefixes had no filtering.

Inbound SAV worse: 67% IPv4 ASes, 74.2% IPv6 ASes had at least one prefix not filtering inbound spoofed packets.

No improvement since 2006: 18.3% IPv4/24 prefixes unfiltered in May 2006 vs 14.9% in August 2019.

Methodology: Spoofer client testing, daemonized for continuous measurements, both IPv4 and IPv6, accounts for NAT behavior.

Data challenges: Sparse sampling (44% of IPv4 /24 prefixes only one week of data), crowd-sourced bias toward security-conscious networks.

NAT: 86.8% of IPv4 ASes tested involved NAT; 6.4% of NAT-behind IPv4 /24 prefixes still forwarded spoofed packets.
