---
name: jira-servicenow-ticket-sync-use-both-webhooks-and-periodic-background-jobs-for-r
abstract: "Jira-ServiceNow ticket sync: use both webhooks and periodic background jobs for reliability"
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: ticket-sync-architecture-pattern-webhooks-background-jobs-for-reliability
weight: 1.0
author: cli
links: []
provenance: []
---

When building a ticket sync tool between Jira (company system) and ServiceNow (customer system), use both event-driven webhooks AND periodic background jobs.

**Why both?**
- Webhooks alone are unreliable: HTTP delivery can fail
- Webhooks may not capture all events depending on configuration
- Webhooks can be delayed
- Background jobs provide a safety net: periodic checks ensure no changes are missed, even if webhooks fail

**Architecture approach:**
1. Webhooks: Listen for events (e.g., new ticket in ServiceNow) and trigger immediate sync actions
2. Background jobs: Periodically query both systems for updates and propagate any changes missed by webhooks
3. This dual approach provides reliability, timeliness, and comprehensive coverage
