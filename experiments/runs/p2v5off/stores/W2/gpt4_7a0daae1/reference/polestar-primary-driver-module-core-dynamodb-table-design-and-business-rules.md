---
name: polestar-primary-driver-module-core-dynamodb-table-design-and-business-rules
abstract: "Polestar primary driver module: core DynamoDB table design and business rules"
type: reference
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

Primary driver module is part of Polestar's Vehicle owner and user management service with modules for Registration number, Owner, Primary driver, and Market. The module tracks which Polestar ID is the primary driver of a car. 

DynamoDB table PrimaryDrivers uses VIN as primary key and Timestamp as sort key. Attributes include: PolestarID, System (must match ClientID for API changes), ChangeSource (Event or API), UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for handling multiple sales), EndTimestamp.

Key business rule: POMS (Order Management System) update can only overwrite API update if OrderID is new and not in PreviousOrderIDs list. When car sold multiple times, all previous OrderIDs stored in list. VIN validated against VISTA (Vehicle Internet Sale & Traceability Application), Polestar ID validated via Polestar ID service.
