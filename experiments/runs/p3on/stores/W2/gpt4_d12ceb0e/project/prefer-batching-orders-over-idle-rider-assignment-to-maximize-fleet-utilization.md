---
name: prefer-batching-orders-over-idle-rider-assignment-to-maximize-fleet-utilization
abstract: Prefer batching orders over idle rider assignment to maximize fleet utilization
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

When multiple riders are in contention for a new order (riders en route to or at the restaurant), prefer batching the new order with an existing rider's order over assigning it to an idle rider. This maximizes the total number of orders the fleet can serve. Batching preference is implemented via an Adjusted Total Delivery Time formula that discounts the total delivery time for batched scenarios.
