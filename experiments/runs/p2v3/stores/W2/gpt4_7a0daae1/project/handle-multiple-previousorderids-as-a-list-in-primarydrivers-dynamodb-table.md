---
name: handle-multiple-previousorderids-as-a-list-in-primarydrivers-dynamodb-table
abstract: Handle multiple PreviousOrderIDs as a list in PrimaryDrivers DynamoDB table
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-03-09
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

When a car is sold multiple times, there can be multiple previous primary drivers. Decision: Store PreviousOrderIDs as a list attribute (not single value) to support this. This allows the service to enforce the rule that a POMS event can only register a primary driver if the OrderID is not already in the PreviousOrderIDs list, even when the car has multiple previous owners.
