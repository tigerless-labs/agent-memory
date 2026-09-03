---
created: 2026-09-02T23:21:34.597390435Z
updated: 2026-09-02T23:21:34.597390435Z
weight: 1.0
last_accessed: 2026-09-02T23:21:34.597390435Z
access_count: 0
pinned: false
links: []
abstract: Infinite scroll video feed with CSS snap-to behavior for Svelte app; scroll-snap-type mandatory on container, scroll-snap-align start on items
---

## Infinite Scroll Snap-to Implementation

For a TikTok-like infinite scroll video feed in Svelte, use CSS Scroll Snap Points to ensure each video snaps into place, occupying the entire viewport.

In `Home.svelte`, wrap videos in a `ul` with class `video-feed`:

```html
<ul id="video-list" class="video-feed">
  {#each videos as video}
    <li>
      <VideoPlayer src="{video.url}" videoId="{video.id}" />
    </li>
  {/each}
</ul>
```

CSS styles:

```css
.video-feed {
  list-style-type: none;
  padding: 0;
  margin: 0;
  width: 100%;
  height: 100vh;
  overflow-y: scroll;
  scroll-snap-type: y mandatory;
  -webkit-overflow-scrolling: touch;
}

.video-feed li {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  scroll-snap-align: start;
  scroll-snap-stop: always;
}
```

Key properties:
- `scroll-snap-type: y mandatory` — y-axis snap required
- `scroll-snap-align: start` — snap point at start of each video
- `scroll-snap-stop: always` — stop at snap point even on quick scroll
- `-webkit-overflow-scrolling: touch` — smooth iOS scrolling