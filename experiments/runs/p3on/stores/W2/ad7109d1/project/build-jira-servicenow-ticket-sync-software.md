---
name: build-jira-servicenow-ticket-sync-software
abstract: Build Jira-ServiceNow ticket sync software
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-22
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Boss assigned project to build software that keeps tickets in sync between company Jira instance and customer ServiceNow instance. Requirements:
- Bidirectional sync: when customer creates ticket in ServiceNow → auto-create in Jira
- When ticket updated in Jira → changes propagate to ServiceNow
- Needs to handle ticket creation and updates
