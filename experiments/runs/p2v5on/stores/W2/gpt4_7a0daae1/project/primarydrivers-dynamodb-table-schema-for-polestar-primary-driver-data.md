---
name: primarydrivers-dynamodb-table-schema-for-polestar-primary-driver-data
abstract: PrimaryDrivers DynamoDB table schema for Polestar primary driver data
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

**Table**: PrimaryDrivers

**Keys**:
- **Primary key (VIN)**: string - identifies the car
- **Sort key (Timestamp)**: string - when primary driver was registered/updated

**Attributes**:
- **PolestarID**: string - Polestar ID of the primary driver
- **System**: string - name of system that initiated change (e.g., POMS, Polestar app, Change of Ownership)
- **ChangeSource**: string - source of change (Event or API)
- **UserID**: string - user ID who made update (if Polestar ID auth API used)
- **ClientID**: string - client ID of service that made change (if M2M auth used)
- **EventID**: string - event ID that caused the change (if event-based)
- **EventTimestamp**: string - timestamp when event was emitted (if event-based)
- **OrderID**: string - order ID from event (if primary driver registered from POMS event)
- **PreviousOrderIDs**: list - previous order IDs (can be multiple if car sold multiple times)
- **EndTimestamp**: string - timestamp when primary driver was removed/replaced

**Notes**: Table stores full history with sort key on timestamp. Multiple rows per VIN track ownership changes over time.
