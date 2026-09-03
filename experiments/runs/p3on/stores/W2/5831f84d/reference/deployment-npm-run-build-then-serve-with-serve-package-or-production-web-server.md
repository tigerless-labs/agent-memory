---
name: deployment-npm-run-build-then-serve-with-serve-package-or-production-web-server
abstract: "Deployment: npm run build, then serve with 'serve' package or production web server"
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

**Build process**:
```bash
npm install              # install dependencies
npm run build            # creates optimized build/ folder
```

**Quick local serve** (development/testing):
```bash
npm install -g serve     # one-time global install
serve public             # serves from build folder, default port 5000
serve public -p 3000     # custom port
```

**Production deployment**:
- Use production-grade web server: Nginx, Apache, or Node.js (Express)
- Configure domain and SSL certificates
- Point web server to the `build` folder for static files

**Supabase compatibility**: Works seamlessly because Supabase client runs in browser; server just serves static files. Browser makes API calls directly to Supabase backend.
