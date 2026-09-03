---
created: 2026-09-02T23:21:38.265381385Z
updated: 2026-09-02T23:21:38.265381385Z
weight: 1.0
last_accessed: 2026-09-02T23:21:38.265381385Z
access_count: 0
pinned: false
links: []
abstract: Dark classy Netflix-like color scheme for Svelte app; background
---

## Netflix-Style Dark Theming

Global CSS in `global.css` or `App.svelte` for dark, classy appearance:

```css
/* Global styles */
body {
  margin: 0;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background-color: #141414;
  color: #fff;
}

h1 {
  font-size: 2rem;
  font-weight: bold;
  color: #fff;
  margin-bottom: 1rem;
}

/* VideoPlayer component styles */
.video-container {
  position: relative;
}

.like-button {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background-color: rgba(255, 255, 255, 0.8);
  border: none;
  border-radius: 5px;
  padding: 5px 10px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.like-button:hover {
  background-color: rgba(255, 255, 255, 1);
}
```

Color palette:
- Background: #141414 (dark charcoal)
- Text: #fff (white)
- Button base: rgba(255, 255, 255, 0.8) (semi-transparent white)
- Button hover: rgba(255, 255, 255, 1) (solid white)
- Font: Helvetica Neue for modern look