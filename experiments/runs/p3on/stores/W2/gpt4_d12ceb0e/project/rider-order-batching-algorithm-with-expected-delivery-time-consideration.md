---
name: rider-order-batching-algorithm-with-expected-delivery-time-consideration
abstract: Rider order batching algorithm with expected delivery time consideration
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

Normalize all metrics to time. For each rider (en route, at restaurant, or idle): calculate Batchability Time Score = (Weight1 × Time-based Frustration Index) + (Weight2 × Additional Wait Time). Frustrated Index is detour time via ETA engine. Additional Wait Time is restaurant wait for second order. Calculate total delivery time: for batched riders, add score to first order's expected delivery time; for idle riders, add ETA to restaurant plus new order's expected delivery time. Apply batching preference: Adjusted Total Delivery Time = Total × (1 - Preference Factor × Rider Status), where Rider Status = 1 for en route/at restaurant, 0 for idle. Rank all riders by Adjusted time and assign to lowest scorer. Tune Weight1, Weight2, Preference Factor based on fleet utilization and customer wait time goals. Consider rider capacity and package compatibility.
