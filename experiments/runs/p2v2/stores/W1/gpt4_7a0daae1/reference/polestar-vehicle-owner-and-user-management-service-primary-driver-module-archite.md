---
name: polestar-vehicle-owner-and-user-management-service-primary-driver-module-archite
abstract: "Polestar Vehicle owner and user management service: primary driver module architecture"
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

Polestar service architecture discussion including: primary driver module (one of four modules alongside registration number, owner, market modules). Key features: tracks primary driver via Polestar ID, captures from POMS (Polestar Order Management System), validates VINs against VISTA (Vehicle Internet Sale & Traceability Application), maintains event store, supports two API versions (M2M auth and Polestar ID auth/OAuth). DynamoDB schema includes VIN (primary key), Timestamp (sort key), PolestarID, System, ChangeSource, UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for multiple sales), EndTimestamp. System names validated (e.g., 'Change of Ownership', 'Polestar app'). POMS updates can overwrite API updates only with new order IDs.
