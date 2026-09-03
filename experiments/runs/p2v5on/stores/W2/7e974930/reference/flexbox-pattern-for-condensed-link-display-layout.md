---
name: flexbox-pattern-for-condensed-link-display-layout
abstract: Flexbox pattern for condensed link display layout
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

User requested reactive HTML/CSS to display a list of links in condensed form using flexbox.

**Solution pattern provided:**
- Container: `display: flex; flex-wrap: wrap`
- Link wrapper: `display: flex; flex-wrap: wrap; justify-content: space-between`
- Individual links: `flex-basis: 30%; margin: 5px; text-align: center`

This creates a responsive grid that wraps links to the next line as needed, distributes them evenly, with each link taking up ~30% of available width and 5px margins.

Reusable for: link collections, tag lists, compact resource displays requiring responsive layout.
