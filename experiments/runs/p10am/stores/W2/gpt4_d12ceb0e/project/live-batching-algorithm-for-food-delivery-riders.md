---
name: live-batching-algorithm-for-food-delivery-riders
abstract: Live batching algorithm for food delivery riders
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-22
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Objective: Optimize last-mile delivery by batching a second order with an existing order for riders en route to or at the restaurant, while giving preference to batching over idle rider assignment to maximize fleet throughput.

Core Metrics:

Time-based Frustration Index: Convert additional distance for second order into time using ETA engine. Measures extra time required for batched route vs. non-batched.

Additional Wait Time: Extra time rider waits at restaurant for second order based on remaining kitchen wait time for first order.

Batchability Time Score = (Weight1 × Time-based Frustration Index) + (Weight2 × Additional Wait Time)

Multi-rider Assignment Logic:

1. For active riders (en route or at restaurant): Calculate Batchability Time Score
2. For idle riders: Calculate ETA to reach restaurant
3. For all riders: Calculate Total Delivery Time
   - Active riders: Batchability Time Score + expected delivery time of first order
   - Idle riders: Rider ETA + expected delivery time of new order
4. Apply batching preference factor:
   Adjusted Total Delivery Time = Total Delivery Time × (1 - Preference Factor × Rider Status)
   (Rider Status = 1 for active, 0 for idle; higher preference factor favors batching)
5. Rank all riders by Adjusted Total Delivery Time (lower is better)
6. Assign to highest-ranked rider; batch if active, assign to idle if idle

Key Considerations: Uses ETA engine to normalize time/distance. Expected delivery time is soft constraint. Weights require tuning based on business goals. Verify rider capacity and package compatibility.
