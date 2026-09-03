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

Building primary driver module as part of Polestar's Vehicle owner and user management service. The service has four modules: Registration number, owner, primary driver, and market modules.

**Primary Driver Module:**
- Tracks the user (identified by Polestar ID) who is the primary driver of a car
- One car can have only one primary driver at a time
- Primary driver captured from Polestar's Order Management System (POMS)
- Listens to order events from POMS
- Validates Polestar IDs against Polestar ID service (API call required)
- Validates VINs against Volvo's Vehicle Internet Sale & Traceability Application (VISTA)
- Stores all events in event store for replay purposes
- Allows systems to change primary driver via API (two versions: M2M auth and Polestar ID/OAuth auth)
- Maintains change history with end timestamps when primary driver changes
- Allows removing primary driver without registering a new one

**Data Storage (DynamoDB):**
- POMS events can only overwrite API updates if the order ID is new
- When making API changes, system must submit valid system name matching client ID (examples: 'Change of Ownership', 'Polestar app')
- Stores related metadata: system name, timestamp registered, user ID (OAuth), client ID (M2M), event ID, event timestamp, order ID, list of previous order IDs, end timestamp
