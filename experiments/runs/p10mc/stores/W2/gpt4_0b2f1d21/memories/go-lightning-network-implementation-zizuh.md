---
created: 2026-09-03T01:36:42.498019323Z
updated: 2026-09-03T01:36:42.498019323Z
weight: 1.0
last_accessed: 2026-09-03T01:36:42.498019323Z
access_count: 0
pinned: false
links:
- zizuh-remittance-startup
abstract: Go implementation for Zizuh - LND node via gRPC, lnrpc package, SendPaymentSync flow, invoice decoding, payment hash verification
---

## Go + Lightning Network Implementation (Zizuh)

**Primary dependencies**:
- github.com/lightningnetwork/lnd/lnrpc — Lightning RPC client
- google.golang.org/grpc — gRPC connection
- golang.org/x/net/context — context for async operations

**Core implementation steps**:

1. Connect to LN node: gRPC connection to LND daemon

2. Decode invoice: Extract payment hash and metadata using client.DecodePayReq()

3. Send payment: Use SendPaymentSync to route through Lightning Network with SendRequest struct

4. Verify completion: Check payment hash matches to confirm success

**Function signature**:
```
func sendRemittance(amount int64, invoice string, nodeAddress string) error
```

**Error handling**: Returns error on insufficient funds, payment routing failure, or node unavailability.

**LND setup**: User needs to run LND node (one of Lightning Network implementations; alternatives: c-lightning, Eclair).

**Related**: zizuh-remittance-startup