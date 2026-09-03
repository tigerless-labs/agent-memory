---
name: auth-required-only-for-send-message-follow-someone-like-post
abstract: "Auth required only for: send message, follow someone, like post"
type: decision
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

**Decision**: Don't require login/signup on page load. Instead, check authentication status only when users attempt to perform specific actions:
- Send a message
- Follow someone
- Like a post

**Implementation**:
- Create `src/lib/auth.js` with `isLoggedIn()` function that checks `supabase.auth.user()`
- In each action handler (like, follow, message), check `isLoggedIn()" before proceeding
- If not logged in, either show login/signup modal or use `svelte-routing` to redirect to /login page
- Unguarded actions: browsing video feed, viewing profiles, reading messages (read-only)
