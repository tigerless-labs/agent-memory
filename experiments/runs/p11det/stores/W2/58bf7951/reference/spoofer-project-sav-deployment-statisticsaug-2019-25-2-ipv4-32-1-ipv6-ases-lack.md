---
name: spoofer-project-sav-deployment-statisticsaug-2019-25-2-ipv4-32-1-ipv6-ases-lack
abstract: "Spoofer Project SAV deployment statistics—Aug 2019: 25.2% IPv4, 32.1% IPv6 ASes lack outbound source address validation"
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

Crowd-sourced research measuring source address validation deployment. Year ending August 1, 2019.

Outbound SAV: 25.2% of IPv4 ASes, 32.1% of IPv6 ASes had prefixes without SAV. Excluding NAT: 14.9% IPv4 /24 prefixes, 30.5% of ASes lacked filtering.

Inbound SAV worse: 67% of IPv4 ASes, 74.2% of IPv6 ASes not filtering inbound spoofed packets.

Historical: May 2006 showed 18.3-20.4% without SAV. No improvement over ~13 years.

Methodology challenges: opt-in bias, sparse coverage. NAT present in 86.8% of ASes; 6.4% of NAT-behind prefixes still forward spoofed packets.
