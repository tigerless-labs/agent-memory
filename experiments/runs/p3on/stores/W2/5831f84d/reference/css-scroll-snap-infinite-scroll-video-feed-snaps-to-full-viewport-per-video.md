---
name: css-scroll-snap-infinite-scroll-video-feed-snaps-to-full-viewport-per-video
abstract: "CSS scroll snap: infinite scroll video feed snaps to full viewport per video"
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

**Technique**: CSS Scroll Snap Points for infinite scroll video feed

**Container (.video-feed)**:
```css
.video-feed {
  list-style-type: none;
  padding: 0;
  margin: 0;
  width: 100%;
  height: 100vh;
  overflow-y: scroll;
  scroll-snap-type: y mandatory;
  -webkit-overflow-scrolling: touch;  /* smooth scroll on iOS */
}
```

**Child items (.video-feed li)**:
```css
.video-feed li {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  scroll-snap-align: start;
  scroll-snap-stop: always;  /* stops at each video even when scrolling fast */
}
```

**Effect**: Each video occupies full viewport and snaps into place as user scrolls, creating TikTok/Instagram Reels-like experience
