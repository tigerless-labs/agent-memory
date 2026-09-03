---
name: user-event-tracking-is-best-done-client-side-with-javascript-listening-for-serve
abstract: User event tracking is best done client-side with JavaScript listening for server responses
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

Analytics event tracking should be implemented on the **client side using JavaScript**, not server-side alone.

**Why:** Client-side tracking can detect the server response in real-time and record events immediately, ensuring accuracy. Server-side tracking introduces delays that can cause inaccurate data if users navigate away before the event is logged.

**Pattern:** Attach event handlers to successful server responses (via AJAX callbacks) so tracking fires when the action is confirmed to have succeeded.
