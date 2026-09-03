---
name: system-name-validation-for-polestar-primary-driver-api-changes
abstract: System name validation for Polestar primary driver API changes
type: procedure
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

When a change to primary driver is made via API, the requesting system must submit a valid system name that matches the ClientID. The system name is stored in the 'System' attribute of the DynamoDB record. Valid examples: 'Change of Ownership', 'Polestar app'. This applies to both M2M authentication and Polestar ID authentication (OAuth) API calls.
