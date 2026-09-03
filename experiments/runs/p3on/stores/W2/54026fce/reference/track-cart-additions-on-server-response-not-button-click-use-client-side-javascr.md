---
name: track-cart-additions-on-server-response-not-button-click-use-client-side-javascr
abstract: "Track cart additions on server response, not button click; use client-side JavaScript"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

When tracking whether users have added items to cart in analytics:

**What to track:** Track on server response (success confirmation), not button click alone. Button clicks are unreliable since users may navigate away before server responds, causing inaccurate data.

**How to implement:** Use client-side JavaScript (not server-side). JS sends AJAX request to server when user clicks Add to Cart button. JS listens for server success response and fires tracking event/analytics code upon successful response.

**Why client-side:** Ensures real-time detection of actual server-side success, accurately reflects whether item was actually added, avoids delays in server-side tracking, and data reflects actual user behavior on the page.

**General principle:** When tracking user behavior, always track both the actions taken AND the success of those actions for comprehensive understanding.
