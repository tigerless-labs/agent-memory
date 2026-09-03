---
created: 2026-09-02T21:26:12.532899775Z
updated: 2026-09-02T21:26:12.532899775Z
weight: 1.0
last_accessed: 2026-09-02T21:26:12.532899775Z
access_count: 0
pinned: false
links: []
abstract: 2023-03-24 flexbox-based layout for displaying large list of links in condensed form, responsive with flex-basis 30% and flex-wrap
---

## Flexbox Link List Layout

User request: Display a large list of links in condensed form using flexbox.

### HTML Structure
```html
<div class="container">
  <div class="link-container">
    <a href="#" class="link">Link 1</a>
    <a href="#" class="link">Link 2</a>
    <!-- More links -->
  </div>
</div>
```

### CSS Pattern
```css
.container {
  display: flex;
  flex-wrap: wrap;
}

.link-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
}

.link {
  flex-basis: 30%;
  margin: 5px;
  text-align: center;
}
```

### Key Properties
- `flex-wrap: wrap` — wraps links to next line when needed
- `flex-basis: 30%` — each link takes ~30% of available width (3 columns at full width)
- `justify-content: space-between` — distributes space evenly
- `margin: 5px` — spacing around each link
- Responsive: links reflow as viewport shrinks