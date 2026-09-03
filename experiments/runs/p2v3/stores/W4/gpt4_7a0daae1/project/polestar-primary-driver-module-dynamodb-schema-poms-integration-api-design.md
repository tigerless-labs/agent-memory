---
name: polestar-primary-driver-module-dynamodb-schema-poms-integration-api-design
abstract: "Polestar primary driver module: DynamoDB schema, POMS integration, API design"
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

Part of Polestar Vehicle Owner and User Management Service (4 modules: Registration number, owner, primary driver, market). Tracks which Polestar ID is primary driver of a car.

Data sources: POMS (Order Management System) events and API (M2M auth or Polestar ID auth/OAuth). Validation: Polestar IDs via Polestar ID service, VINs via Volvo VISTA.

DynamoDB table PrimaryDrivers has Primary Key=VIN, Sort Key=Timestamp. Attributes: PolestarID, System (name of system initiating change, e.g. Change of Ownership or Polestar app), ChangeSource (Event or API), UserID, ClientID, EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for multiple car sales), EndTimestamp.

Business rules: POMS events only register if OrderID is new; API changes need valid system name matching ClientID; event store for replay; history tracked with end timestamps; can remove primary driver without registering new one.
