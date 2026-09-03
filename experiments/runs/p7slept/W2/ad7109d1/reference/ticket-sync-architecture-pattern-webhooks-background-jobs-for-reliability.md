---
name: ticket-sync-architecture-pattern-webhooks-background-jobs-for-reliability
abstract: "Ticket sync architecture pattern: webhooks + background jobs for reliability"
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

## Webhook Limitations & Why Background Jobs Are Needed

**Webhook reliability issues:**
1. **Delivery failures**: Webhooks rely on HTTP requests; infrastructure issues can prevent delivery
2. **Incomplete coverage**: Webhooks only trigger for configured event types; some updates may be missed
3. **Timing delays**: Depending on webhook configuration, delay between event and action can occur
4. **Single point of failure**: If webhook delivery fails, that change never propagates

**Solution: Layered approach**

Use webhooks for near-real-time updates + background job for comprehensive safety:

- **Webhooks (immediate)**: Fast response to most updates via event notifications
- **Background Job (periodic)**: 
  - Run on regular intervals (e.g., every 5-15 minutes)
  - Query both Jira and ServiceNow for any updates since last run
  - Catch any changes missed by webhook delivery failures
  - Ensure consistency and completeness
  - Acts as a reconciliation mechanism

**Implementation options for background job:**
- Cron job running a script at regular intervals
- Message queue-based system with scheduled trigger
- Both approaches can work; message queue offers better scalability/decoupling
