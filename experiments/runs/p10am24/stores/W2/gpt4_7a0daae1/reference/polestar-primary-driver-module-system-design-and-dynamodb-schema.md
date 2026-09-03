---
name: polestar-primary-driver-module-system-design-and-dynamodb-schema
abstract: Polestar Primary Driver module - system design and DynamoDB schema
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

# Polestar Primary Driver Module
## Service Context
Part of Polestar's Vehicle owner and user management service (four modules: Registration number, Owner, Primary driver, Market).
## Purpose
Tracks which user (identified by Polestar ID) is the primary driver of a car. A car can have only one primary driver.
## Data Sources
POMS (Polestar Order Management System) listens to order events. Polestar IDs validated via Polestar ID service API. VINs validated via VISTA (Volvo factory order system). APIs support M2M auth and Polestar ID auth (OAuth). All events stored in event store for replay.
## DynamoDB Schema
Primary Key: VIN (string). Sort Key: Timestamp (string).
Attributes: PolestarID, System (name of system making change - must be valid and match ClientID), ChangeSource (Event or API), UserID (Polestar ID auth), ClientID (M2M auth), EventID, EventTimestamp, OrderID, PreviousOrderIDs (list for multiple sales), EndTimestamp.
## Business Rules
POMS can overwrite API only if OrderID is new. Previous driver gets end timestamp when replaced. Can remove driver without replacing. Full history maintained.
