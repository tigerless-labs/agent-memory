---
name: polestar-primary-driver-module-dynamodb-schema-and-business-logic
abstract: "Polestar primary driver module: DynamoDB schema and business logic"
type: fact
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

Polestar Vehicle owner and user management service primary driver module tracks the Polestar ID holder as the primary driver of a car. Part of service with 4 modules: Registration number, owner, primary driver, market. Data from POMS (Order Management System) and API. DynamoDB table PrimaryDrivers uses VIN as primary key and Timestamp as sort key. Key attributes: PolestarID, System (must be valid and match ClientID), ChangeSource (Event/API), UserID (Polestar ID auth), ClientID (M2M auth), EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for multiple ownership changes), EndTimestamp. Validation via Polestar ID service and VISTA. Rules: POMS can only register if OrderID is new, previous driver gets EndTimestamp on change, can remove without registering new driver, all events in event store for replay.
