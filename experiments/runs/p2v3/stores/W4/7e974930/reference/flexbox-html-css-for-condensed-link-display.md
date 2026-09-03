---
name: flexbox-html-css-for-condensed-link-display
abstract: Flexbox HTML/CSS for condensed link display
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

Date: 2023-03-24

Problem: Display a list of links in condensed responsive form using flexbox.

Solution:
HTML uses nested divs (.container and .link-container) with anchor elements (.link) inside.

CSS approach:
- Container and link-container both use display: flex with flex-wrap: wrap
- justify-content: space-between distributes links evenly across row
- Each link has flex-basis: 30% (takes one-third of available space)
- 5px margin around each link for spacing
- text-align: center centers text within each link

Result: Links automatically wrap to next line as needed with even distribution.
