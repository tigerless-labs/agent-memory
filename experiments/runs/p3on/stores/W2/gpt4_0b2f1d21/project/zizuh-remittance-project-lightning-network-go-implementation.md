---
name: zizuh-remittance-project-lightning-network-go-implementation
abstract: "Zizuh remittance project — Lightning Network, Go implementation"
type: fact
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

Zizuh is a remittance service project positioned as a competitor to Strike, using Bitcoin Lightning Network for cross-border payments.

Architecture: Converts fiat to BTC on Lightning Network, routes via LND node, converts back to recipient's local fiat currency.

Core function signature: sendRemittance(amount, originWallet, destinationWallet)

Technical stack: Go language, LND (Lightning Network Daemon) with gRPC client, invoice generation and payment verification.

Implementation flow: Connect to LN node via gRPC → decode invoice → send payment request → stream status verification → error handling and confirmation.
