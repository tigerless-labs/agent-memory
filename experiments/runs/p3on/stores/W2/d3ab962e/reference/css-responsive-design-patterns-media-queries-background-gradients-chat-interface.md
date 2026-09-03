---
name: css-responsive-design-patterns-media-queries-background-gradients-chat-interface
abstract: "CSS responsive design patterns: media queries, background gradients, chat interfaces"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2022-09-24
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

CSS techniques for responsive chat interfaces:

**Full-viewport backgrounds:**
- Set body: margin 0, padding 0
- Use position: absolute; top: 0; left: 0; right: 0; bottom: 0 to fill entire viewport

**Infinite backgrounds (color-based):**
- Use linear-gradient(to bottom, #color1 0%, #color2 80%, #color3 80%, #color4 100%)
- Set background-size: 100% 100vh

**Icons with pseudo-elements:**
- Use :before/:after with position: absolute
- Position relative to parent with position: relative
- Example: left: -30px, top: 50%, transform: translateY(-50%) for centering

**Mobile responsiveness:**
- Use @media only screen and (max-width: 600px)
- Adjust width: 100% for small screens
- Set max-width: 100% on message elements

**Chat bubble styling:**
- Use display: inline-block for message containers
- max-width: 70% to prevent full-width messages
- border-radius for rounded corners
- Semi-transparent backgrounds: rgba(255, 255, 255, 0.9)
