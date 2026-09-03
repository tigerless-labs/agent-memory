---
name: polestar-primary-driver-module-architecture-and-data-flow
abstract: Polestar primary driver module architecture and data flow
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

Tracks which Polestar ID is the primary driver of a car (one per car). Data sources: POMS events and APIs (M2M and OAuth). Validates Polestar ID existence and VIN in VISTA. Maintains event store for replay, allows external systems to update via API, maintains driver history with end timestamps.
