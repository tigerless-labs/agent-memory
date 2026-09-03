---
name: flexbox-approach-for-displaying-condensed-link-lists
abstract: Flexbox approach for displaying condensed link lists
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

## Solution for reactive link display

When the user needs to display a list of links in condensed form:

**Container layout:**
- Use `display: flex; flex-wrap: wrap;`
- Set `justify-content: space-between` to distribute links evenly

**Link sizing:**
- Use `flex-basis: 30%` to control link width
- Add `margin: 5px` for breathing room

**Full CSS example:**
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

This creates rows that wrap naturally, distributing multiple links evenly and compactly.

First suggested: 2023-03-24 (old pattern, may still be useful for similar requests)
