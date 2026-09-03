---
name: zizuh-technical-stack-go-bitcoin-lightning-network-lnd
abstract: "Zizuh technical stack: Go + Bitcoin Lightning Network (LND)"
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

Technology choices for Zizuh remittance service:
- Language: Go
- Network: Bitcoin Lightning Network
- LND implementation for Lightning node
- Connect to LND via gRPC

Core function to implement: `sendRemittance(amount, originWallet, destinationWallet)`
- Verify sufficient balance in origin wallet
- Deduct from origin wallet
- Add to destination wallet
- Integrate with Lightning Network invoice/payment system
- Decode Lightning Network invoice to get payment hash
- Send payment via Lightning node
- Verify payment status and return result
