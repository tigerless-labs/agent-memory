---
name: primary-driver-dynamodb-table-schema
abstract: Primary driver DynamoDB table schema
type: reference
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

Table: PrimaryDrivers. Key: VIN + Timestamp. Attributes: PolestarID, System, ChangeSource, UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for multi-sale tracking), EndTimestamp.
