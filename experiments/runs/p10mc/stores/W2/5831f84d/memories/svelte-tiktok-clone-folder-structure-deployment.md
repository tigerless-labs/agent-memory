---
created: 2026-09-02T23:21:42.743386906Z
updated: 2026-09-02T23:21:42.743386906Z
weight: 1.0
last_accessed: 2026-09-02T23:21:42.743386906Z
access_count: 0
pinned: false
links: []
abstract: Svelte TikTok clone folder structure; npm run build produces build/ folder; serve public -p 3000 to serve; works with Supabase via client-side API calls
---

## Project Folder Structure

```
my-tiktok-clone/
├── public/
│   ├── global.css
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Conversations.svelte
│   │   ├── Home.svelte
│   │   ├── Login.svelte
│   │   ├── Messages.svelte
│   │   ├── Signup.svelte
│   │   └── VideoPlayer.svelte
│   ├── lib/
│   │   └── supabase.js
│   │   └── auth.js
│   ├── App.svelte
│   └── main.js
├── package.json
└── README.md
```

## Running on a Server

1. Install dependencies:
   ```bash
   npm install
   ```

2. Build for production:
   ```bash
   npm run build
   ```
   Creates optimized `build/` folder in `public/`

3. Serve locally (development/testing):
   ```bash
   npm install -g serve
   serve public -p 3000
   ```
   Default port: 5000; use `-p` flag to change

## Supabase Integration

The app works with Supabase because it's a client-side library communicating via HTTP requests. The browser runs the JavaScript code, including Supabase client, regardless of which server serves the static files.

Supabase client initialized in `src/lib/supabase.js` with API URL and anon key from project dashboard.