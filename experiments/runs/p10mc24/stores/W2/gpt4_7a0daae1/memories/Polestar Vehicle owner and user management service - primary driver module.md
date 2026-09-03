---
created: 2026-09-02T21:38:05.932442064Z
updated: 2026-09-02T21:38:05.932442064Z
weight: 1.0
last_accessed: 2026-09-02T21:38:05.932442064Z
access_count: 0
pinned: false
links: []
abstract: Polestar primary driver module tracks car ownership; VIN primary key; DynamoDB stores PolestarID, System name (POMS, Polestar app, Change of Ownership), ChangeSource (Event/API), UserID, ClientID, EventID, OrderID, PreviousOrderIDs list, timestamps; POMS events override API updates only if OrderID is new; maintains history with EndTimestamp
---

## Overview

The **primary driver module** is part of Polestar's "Vehicle owner and user management service" which has four modules: Registration number, owner, primary driver, and market modules.

## Purpose

Tracks the user (identified by Polestar ID) who is the primary driver of a car (identified by VIN). A car can only have one primary driver.

## Data Sources

**Primary source**: Polestar's Order Management System (POMS)
- Service listens to order events from POMS
- Valid Polestar ID must exist in the Polestar ID service (confirmed via API)
- Valid VIN must exist in Volvo's VISTA (Vehicle Internet Sale & Traceability Application)
- If order event contains valid VIN and Polestar ID in "Driver" field, that ID becomes the car's primary driver

**Secondary source**: APIs
- M2M authentication API (uses ClientID)
- Polestar ID authentication API using OAuth (requires user credentials)
- With Polestar ID auth, user can only edit primary driver if they have logged-in credentials access

## Event Storage

Service stores all received events in an "event store" for replay purposes.

## DynamoDB Table: PrimaryDrivers

**Primary key**: VIN (string)
**Sort key**: Timestamp (string)

### Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| VIN | string | Car identifier; primary key |
| Timestamp | string | When primary driver was registered/updated; sort key |
| PolestarID | string | Polestar ID of the current primary driver |
| System | string | Name of system that initiated change (must be valid and match ClientID for API updates; examples: "POMS", "Polestar app", "Change of Ownership") |
| ChangeSource | string | Source of change: "Event" (from POMS) or "API" |
| UserID | string | User ID of person making update (only for Polestar ID auth API) |
| ClientID | string | Client ID of service making change (only for M2M auth API) |
| EventID | string | ID of event that caused change (if change was event-based) |
| EventTimestamp | string | Timestamp when event was emitted (if change was event-based) |
| OrderID | string | Order ID from event (if primary driver registered from POMS event) |
| PreviousOrderIDs | list | List of previous order IDs (handles multiple sales; examples: [o1], [o1, o2]) |
| EndTimestamp | string | Timestamp when previous primary driver was removed |

## Business Rules

1. **One primary driver per car**: When a new primary driver is registered, the previous primary driver gets an EndTimestamp
2. **POMS override rule**: A POMS update can only overwrite an API update if the OrderID is new
3. **API validation**: System name must be valid and match ClientID when submitted through API
4. **Multiple ownership history**: PreviousOrderIDs stored as list to handle car resales
5. **API option to remove without replace**: Possible to remove a primary driver without registering a new one

## Example Data

| VIN | Timestamp | PolestarID | System | ChangeSource | UserID | ClientID | EventID | EventTimestamp | OrderID | PreviousOrderIDs | EndTimestamp |
|-----|-----------|-----------|--------|--------------|--------|----------|---------|-----------------|---------|------------------|--------------|
| 123 | 2022-12-11T12:00:00 | 101 | POMS | Event | | | e1 | 2022-12-11T11:00:00 | o1 | | |
| 123 | 2022-12-11T12:15:00 | 102 | Polestar app | API | u1 | | | | | [o1] | 2022-12-11T12:14:59 |
| 123 | 2022-12-11T12:30:00 | 103 | Change of Ownership | API | u2 | c1 | | | | [o1, o2] | 2022-12-11T12:29:59 |

Example interpretation:
- Entry 1: POMS event registers Polestar ID 101 as primary driver with order o1
- Entry 2: Polestar app update via API changes primary driver to 102; previous order o1 stored
- Entry 3: Change of Ownership system changes primary driver to 103; multiple previous orders o1 and o2 stored (car was resold)