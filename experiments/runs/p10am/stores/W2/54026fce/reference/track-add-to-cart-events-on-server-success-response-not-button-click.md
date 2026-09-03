---
name: track-add-to-cart-events-on-server-success-response-not-button-click
abstract: "Track add-to-cart events on server success response, not button click"
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

For e-commerce cart tracking, record the event when the **server responds with success**, not when the user clicks the 'Add to Cart' button.

**Why:** A button click alone is unreliable. Users may navigate away or close the browser before the server processes the request. Only a successful server response confirms the item was actually added.

**Implementation:** Use client-side JavaScript to listen for the server success response and fire the tracking event at that point.
