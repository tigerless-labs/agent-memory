---
name: responsive-chat-interface-css-media-queries-infinite-gradient-backgrounds-mobile
abstract: "Responsive chat interface CSS: media queries, infinite gradient backgrounds, mobile-first layout"
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

CSS patterns for responsive chat interface design from September 2022:

**Mobile responsiveness (600px breakpoint):**
- Desktop: .chat { width: 80%; max-width: 500px; margin: 50px auto; }
- Mobile: .chat { width: 100%; max-width: none; margin: 20px 0; }
- Messages: max-width adjusts from 70% to 100% on small screens

**Infinite background without images:**
Use linear gradient instead of repeating pattern:
```css
body {
  background: linear-gradient(to bottom, #e8e8e8 0%, #e8e8e8 80%, #fff 80%, #fff 100%);
  background-size: 100% 100vh;
  margin: 0;
  padding: 0;
}
```

**Full-page coverage:**
- Set body margin: 0; padding: 0; to remove default spacing
- Use position: absolute; top/left/right/bottom: 0; if needed for full viewport fill

**Message icons:**
- Use CSS pseudo-elements :before/:after with position: absolute
- Position icons left -30px for sender, right -30px for receiver
- Use background-image property or content property with icon
