---
name: polestar-primary-driver-module-dynamodb-schema-with-previousorderids-list
abstract: "Polestar Primary Driver Module: DynamoDB schema with PreviousOrderIDs list"
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

## Context
Designed the Primary Driver Module for Polestar's Vehicle Owner and User Management Service (2023-03-09). The service has four modules: Registration number, owner, primary driver, and market modules.

## Key Design Decisions

### DynamoDB Table Structure
**PrimaryDrivers** table:
- Primary key: VIN
- Sort key: Timestamp
- Attributes: PolestarID, System, ChangeSource, UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list), EndTimestamp

### System Name Validation
- API requests must include system name matching the ClientID
- Examples: "Change of Ownership", "Polestar app"

### Business Rules
- One primary driver per car
- POMS event can only register new primary driver with new order ID
- EndTimestamp marks when previous primary driver was removed

## Problem Solved
**Multiple previous owners**: Changed PreviousOrderID (single) to PreviousOrderIDs (list) to track multiple car sales while enforcing POMS update rules.
