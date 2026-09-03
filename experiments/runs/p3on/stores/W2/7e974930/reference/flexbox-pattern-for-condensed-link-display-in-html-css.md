---
name: flexbox-pattern-for-condensed-link-display-in-html-css
abstract: Flexbox pattern for condensed link display in HTML/CSS
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

Code pattern for displaying a list of links in a reactive, condensed HTML/CSS layout using flexbox.

HTML structure with link-container using flexbox with wrap, each link at 30% width, 5px margin, center-aligned.

CSS:
- .container: display flex, flex-wrap wrap
- .link-container: display flex, flex-wrap wrap, justify-content space-between  
- .link: flex-basis 30%, margin 5px, text-align center

Effect: links wrap to next line as needed, distribute evenly across row, condensed spacing.
