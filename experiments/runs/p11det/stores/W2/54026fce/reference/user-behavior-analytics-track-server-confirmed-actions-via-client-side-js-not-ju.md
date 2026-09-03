---
name: user-behavior-analytics-track-server-confirmed-actions-via-client-side-js-not-ju
abstract: "User behavior analytics: track server-confirmed actions via client-side JS, not just button clicks"
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

When tracking user actions in analytics (e.g., adding items to cart), track both the action taken AND whether it succeeded. For cart additions, track when the server responds successfully, not on button click alone. Reason: button clicks alone are unreliable—users may navigate away before the server responds, creating inaccurate data. Use client-side JavaScript to send request, listen for server response confirming success, then fire analytics event. This ensures real-time, accurate tracking.
