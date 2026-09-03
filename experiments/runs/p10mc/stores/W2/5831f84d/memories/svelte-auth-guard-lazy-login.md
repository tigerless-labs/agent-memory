---
created: 2026-09-02T23:21:47.068687560Z
updated: 2026-09-02T23:21:47.068687560Z
weight: 1.0
last_accessed: 2026-09-02T23:21:47.068687560Z
access_count: 0
pinned: false
links: []
abstract: Prompt login/signup only on specific actions (like, follow, message); src/lib/auth.js with isLoggedIn() function; check before action and redirect to /login if needed
---

## Lazy Login: Prompt Auth Only on Action

Only require authentication when users attempt to:
- Send a message
- Follow someone
- Like a post/video

### Setup: `src/lib/auth.js`

```javascript
import supabase from './supabase';

export function isLoggedIn() {
  return supabase.auth.user() !== null;
}
```

### Usage Example: `VideoPlayer.svelte`

```javascript
import { isLoggedIn } from './lib/auth';
import { navigate } from 'svelte-routing';

async function likeVideo() {
  if (!isLoggedIn()) {
    navigate('/login');
    return;
  }

  // Continue with like logic...
}
```

### Alternative: Modal Instead of Redirect

Show a modal with login/signup options instead of redirecting:
- Use a Svelte store to manage modal state
- Emit event when user clicks like/follow/message
- Parent component shows modal if not logged in
- User logs in within modal, then action proceeds

### Apply Same Pattern to:
- Follow buttons (in user profile component)
- Message send buttons (in Messages.svelte)
- Comment/like buttons (in VideoPlayer.svelte)