---
name: polestar-vehicle-owner-and-user-management-service-with-primary-driver-module
abstract: Polestar Vehicle owner and user management service with primary driver module
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

Working on a Polestar vehicle management system with four modules: Registration number, owner, primary driver, and market modules.

**Primary Driver Module:**
- Tracks the primary driver (identified by Polestar ID) for each car
- One car can only have one primary driver
- Source: Polestar's Order Management System (POMS) events
- Validates Polestar IDs via Polestar ID service API
- Validates VINs via Volvo's VISTA (Vehicle Internet Sale & Traceability Application)

**Data Storage:**
- DynamoDB table with VIN (primary key) and Timestamp (sort key)
- Event store for replay purposes
- Attributes: PolestarID, System, ChangeSource, UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list), EndTimestamp

**API Access Methods:**
- M2M authentication
- Polestar ID authentication (OAuth) - user can only edit own primary driver

**Business Rules:**
- System name submitted with API changes must be valid and match client ID (examples: Change of Ownership, Polestar app)
- POMS event can only overwrite API update if order ID is new
- Maintains historical record of primary driver changes
- Previous primary driver gets end timestamp when new driver assigned
- Can remove primary driver without assigning new one
