---
name: polestar-primary-driver-module-tracks-vehicle-owners-via-poms-events-and-api
abstract: Polestar primary driver module tracks vehicle owners via POMS events and API
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

The primary driver module:

**Purpose**: Tracks which user (Polestar ID) is the primary driver of a car. A car can only have one primary driver.

**Data sources**:
- Listens to order events from Polestar's Order Management System (POMS)
- Accepts API calls for changes via M2M or Polestar ID (OAuth) authentication

**Event processing**: When POMS sends an order event with valid VIN and Polestar ID:
- Validates VIN against Volvo's VISTA (Vehicle Internet Sale & Traceability Application)
- Validates Polestar ID exists in Polestar ID service
- Saves the Polestar ID as primary driver
- Stores all events in event store for replay

**API access**:
- M2M authentication: client ID-based, system name must match client ID
- Polestar ID auth (OAuth): user can only edit if they have access to logged-in primary driver's credentials

**Change metadata**: System records:
- System name that made change (e.g., 'POMS', 'Polestar app', 'Change of Ownership')
- Timestamp of registration
- User ID (if Polestar ID auth) or Client ID (if M2M auth)
- Event ID and emission timestamp (if event-driven)
- Order ID (if from POMS event)

**Business rule**: POMS update can only overwrite API update if order ID is new.

**History tracking**: Previous primary driver gets end timestamp when new one is registered. Can remove primary driver via API without registering replacement.
