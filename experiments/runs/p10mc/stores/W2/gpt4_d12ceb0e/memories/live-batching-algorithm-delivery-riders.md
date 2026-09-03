---
created: 2026-09-02T23:40:05.206542669Z
updated: 2026-09-02T23:40:05.206542669Z
weight: 1.0
last_accessed: 2026-09-02T23:40:05.206542669Z
access_count: 0
pinned: false
links: []
abstract: Food delivery order batching algorithm. Ranks riders (active and idle) to assign new orders. Prefers batching with en-route/at-restaurant riders to maximize fleet throughput. Factors combined via Time-based Frustration Index, Additional Wait Time, expected delivery time. Adjusted Total Delivery Time formula includes Preference Factor to bias toward batching.
---

## Live Batching Algorithm for Delivery Riders

**Objective:** Batch new orders with riders en route to or at the restaurant to maximize the number of orders served with the same fleet size, rather than assigning to idle riders.

### Key Inputs
- ETA engine available to predict travel time point A → B
- Expected delivery time for every order (not a hard constraint, but influences decision)
- Multiple rider types: en route to restaurant, already at restaurant, idle
- Constraints: rider capacity and package compatibility apply

### Algorithm Steps

1. **Calculate Time-based Frustration Index** for each active rider (en route/at restaurant):
   - Use ETA engine to convert additional distance from second order into time
   - Measures extra time needed for batched route vs non-batched route

2. **Calculate Additional Wait Time** for each active rider:
   - Extra time rider waits at restaurant for second order
   - Based on remaining kitchen wait time for first order

3. **Calculate Batchability Time Score** for each active rider:
   ```
   Batchability Time Score = (Weight1 × Time-based Frustration Index) + (Weight2 × Additional Wait Time)
   ```
   - Weight1, Weight2 represent relative importance of route efficiency vs wait time

4. **Calculate restaurant ETA** for each idle rider:
   - Use ETA engine to determine time to reach restaurant

5. **Calculate Total Delivery Time** for all riders if they pick up new order:
   - Active riders: Batchability Time Score + expected delivery time of first order
   - Idle riders: ETA to restaurant + expected delivery time of new order

6. **Apply Preference Factor for batching** to create Adjusted Total Delivery Time:
   ```
   Adjusted Total Delivery Time = Total Delivery Time × (1 - Preference Factor × Rider Status)
   ```
   - Rider Status: 1 if active (en route/at restaurant), 0 if idle
   - Preference Factor: tunable value that biases toward batching

7. **Rank all riders** by Adjusted Total Delivery Time (lower is better)

8. **Assign order** to highest-ranked rider
   - If active rider: create batch
   - If idle rider: send for single order

### Tuning Parameters
- Weight1, Weight2: balance route efficiency vs wait times
- Preference Factor: controls how much to favor batching over idle riders
- Monitor and adjust based on fleet utilization, customer satisfaction, delivery times

### Constraints to Apply
- Rider capacity limits
- Package compatibility rules