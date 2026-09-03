---
created: 2026-09-03T01:36:26.657024911Z
updated: 2026-09-03T01:36:26.657024911Z
weight: 1.0
last_accessed: 2026-09-03T01:36:26.657024911Z
access_count: 0
pinned: false
links:
- strike-lightning-remittance-model
- go-lightning-network-implementation-zizuh
abstract: May 25 2023 — Zizuh is user's planned remittance company, competitor to Strike; uses Bitcoin Lightning Network for cross-border payments with near-zero fees; target implementation in Go
---

## Zizuh Project

**Type**: Remittance/payment startup (competitor to Strike)

**Core capability**: Send money internationally almost free using Bitcoin Lightning Network, without requiring users to hold Bitcoin directly.

**Business model**: Connect users' bank accounts → convert fiat to Bitcoin on Lightning Network → route to recipient → convert back to recipient's local currency.

**Implementation language**: Go

**Key function signature**:
```go
sendRemittance(amount int64, invoice string, nodeAddress string) error
```

**Architecture**:
- Integrates with Lightning Network node (LND preferred)
- Uses gRPC for node communication
- Decodes Lightning invoices to extract payment hashes
- Routes payments through LN for settlement
- Verifies payment completion using payment hash matching

**Status**: Planning/design phase (discussed May 25, 2023)