---
name: html-css-flexbox-pattern-for-condensed-responsive-link-display
abstract: HTML/CSS flexbox pattern for condensed responsive link display
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-03-24
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

**HTML Structure:**
```html
<div class="container">
  <div class="link-container">
    <a href="#" class="link">Link 1</a>
    <a href="#" class="link">Link 2</a>
    <a href="#" class="link">Link 3</a>
  </div>
</div>
```

**CSS:**
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

**Key features:**
- Links wrap to next line as space allows
- Distributed evenly across row via `justify-content: space-between`
- Each link takes 30% of available space
- 5px margin around each link
- Center-aligned text
- Responsive and condensed layout

**Use case:** Displaying many links in space-efficient, responsive format
