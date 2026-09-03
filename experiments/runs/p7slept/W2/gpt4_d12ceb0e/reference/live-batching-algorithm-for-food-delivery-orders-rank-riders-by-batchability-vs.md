---
name: live-batching-algorithm-for-food-delivery-orders-rank-riders-by-batchability-vs
abstract: "Live batching algorithm for food delivery orders: rank riders by batchability vs idle assignment"
type: reference
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

## Problem
Optimize assignment of new orders to riders in contention: batch with existing rider (en route to or at restaurant) vs assign to idle rider.

## Business Goal
Prefer batching to increase fleet utilization (more orders served with same fleet size).

## Algorithm Components

**For each en-route/at-restaurant rider:**
- Time-based Frustration Index: convert additional route distance to time via ETA engine
- Additional Wait Time: extra restaurant wait for second order based on kitchen wait remaining
- Batchability Time Score = (Weight1 × Time-based Frustration Index) + (Weight2 × Additional Wait Time)

**For each idle rider:**
- Calculate ETA to reach restaurant

**For all riders:**
- Total Delivery Time = Batchability Score + expected delivery time of first order (if batching) OR ETA + expected delivery time of new order (if idle)
- Adjusted Total Delivery Time = Total Delivery Time × (1 - Preference Factor × Rider Status)
  - Rider Status = 1 if en-route/at-restaurant, 0 if idle
  - Preference Factor reduces score for batching candidates, making them preferred

**Assignment:**
- Rank all riders by Adjusted Total Delivery Time (lower is better)
- Assign new order to highest-ranked rider
- Create batch if assigned to en-route/at-restaurant rider, else send idle rider to restaurant

## Considerations
- Rider capacity and package compatibility must be checked before assignment
- Weight1, Weight2, and Preference Factor require tuning based on business goals
- Algorithm developed but not yet validated; user wanted to step through before finalizing
