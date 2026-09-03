---
name: flexbox-html-css-for-displaying-lists-of-links-in-condensed-form
abstract: Flexbox HTML/CSS for displaying lists of links in condensed form
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

HTML and CSS using flexbox for a condensed, responsive list of links layout.

HTML:
```html
<div class="container">
  <div class="link-container">
    <a href="#" class="link">Link 1</a>
    <a href="#" class="link">Link 2</a>
    <a href="#" class="link">Link 3</a>
    <!-- Add more links here -->
  </div>
</div>
```

CSS:
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
- Uses flexbox with `flex-wrap: wrap` for responsive wrapping
- Links distributed evenly with `justify-content: space-between`
- Each link takes 30% width with 5px margin
- Condenses link display for lists with many items
