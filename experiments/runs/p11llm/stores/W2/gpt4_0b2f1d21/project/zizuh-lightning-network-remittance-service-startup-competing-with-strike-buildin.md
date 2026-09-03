---
name: zizuh-lightning-network-remittance-service-startup-competing-with-strike-buildin
abstract: "Zizuh: Lightning Network remittance service startup competing with Strike, building in Go"
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-25
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Project: Zizuh

A remittance service company designed to compete with Strike. Uses Bitcoin's Lightning Network to enable instant, low-cost cross-border payments.

### Technical Approach
- Language: Go
- Network: Bitcoin Lightning Network
- Core Architecture: Connects users' bank accounts → converts to Bitcoin on Lightning Network → sends to recipient → converts back to local currency
- Key Implementation: LND (Lightning Network Daemon) via gRPC

### Core Function
Function: sendRemittance(amount int64, invoice string, nodeAddress string)

Features:
- Decodes Lightning Network invoices
- Verifies sufficient funds
- Routes payments via Lightning Network
- Handles payment verification and error reporting

### Goal
Provide zero-cost remittance payments by leveraging Lightning Network capabilities without requiring users to directly handle Bitcoin the asset.
