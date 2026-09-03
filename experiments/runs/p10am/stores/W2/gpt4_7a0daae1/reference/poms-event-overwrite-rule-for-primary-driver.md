---
name: poms-event-overwrite-rule-for-primary-driver
abstract: POMS event overwrite rule for primary driver
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

POMS events can only register a new primary driver if order ID is new (not in PreviousOrderIDs). A new POMS order ID can overwrite previous API-initiated updates but cannot duplicate existing order IDs.
