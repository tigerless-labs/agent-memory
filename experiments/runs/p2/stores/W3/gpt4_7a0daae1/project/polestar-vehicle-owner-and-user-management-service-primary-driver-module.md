---
name: polestar-vehicle-owner-and-user-management-service-primary-driver-module
abstract: Polestar Vehicle Owner and User Management Service - primary driver module
type: fact
status: active
created: 2026-09-01
updated: 2026-09-01
valid_from: 2026-09-01
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Manages vehicle ownership tracking for Polestar. Service has four modules: Registration number, owner, primary driver, and market. Primary driver module tracks users by Polestar ID. Data sourced from POMS (Order Management System). Validates VINs against Volvo's VISTA system. Stores all events in event store for replay. Supports two API authentication versions: M2M and Polestar ID OAuth. System names like 'Change of Ownership' and 'Polestar app' required for M2M auth. DynamoDB storage with VIN as primary key, Timestamp as sort key. Maintains primary driver history with end timestamps. POMS events can only overwrite API updates if order ID is new. Handles multiple previous order IDs (vehicle resale scenarios).
