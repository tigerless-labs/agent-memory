---
name: polestar-primary-driver-module-dynamodb-schema-and-attributes
abstract: Polestar Primary Driver module DynamoDB schema and attributes
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

DynamoDB table stores primary driver data with attributes: VIN (primary key), Timestamp (sort key), PolestarID, System, ChangeSource, UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list), EndTimestamp. Module part of Vehicle Owner and User Management Service.
