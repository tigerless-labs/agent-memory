---
name: building-tiktok-clone-app-with-svelte-and-supabase-backend
abstract: Building TikTok clone app with Svelte and Supabase backend
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

Project: my-tiktok-clone

- **Framework**: Svelte
- **Backend**: Supabase (client-side library for auth, database, real-time)
- **Main features**: infinite scroll video feed, user authentication, messaging, follow functionality, like/heart system
- **Folder structure**: public/, src/components/, src/lib/, with components for Home, VideoPlayer, Login, Signup, Messages, Conversations
- **Styling**: dark theme with CSS scroll snap for video feed snap-to experience
- **Deployment**: npm build for production, served via `serve` package or production web server (Nginx/Apache)
