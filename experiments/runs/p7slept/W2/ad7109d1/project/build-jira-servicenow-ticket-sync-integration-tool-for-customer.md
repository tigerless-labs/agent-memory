---
name: build-jira-servicenow-ticket-sync-integration-tool-for-customer
abstract: Build Jira-ServiceNow ticket sync integration tool for customer
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

Boss requested building software to keep tickets in sync between:
- **Jira** (company's internal ticketing system)
- **ServiceNow** (customer's ticketing system)

**Sync requirements:**
- When customer creates ticket in ServiceNow → software creates corresponding ticket in Jira
- When someone updates ticket in Jira → changes propagate to ServiceNow
- Bidirectional synchronization

**Identified module architecture:**
1. **API Integration**: Handle Jira and ServiceNow API calls (CRUD operations on tickets)
2. **Webhooks**: Configuration and management of event listeners for both systems
3. **Ticket Sync**: Core syncing logic + database to track ticket relationships between systems
4. **User Interface**: Configure which projects/fields sync between systems
5. **Background Job**: Periodic checks for updates as reliability safeguard

See decision: Jira-ServiceNow webhook + background job reliability pattern
