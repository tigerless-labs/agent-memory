---
name: flexbox-pattern-for-condensed-reactive-link-list-display
abstract: Flexbox pattern for condensed reactive link list display
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

Use case: displaying lists of links in condensed, responsive form

Key CSS properties:
- display: flex with flex-wrap: wrap for responsive layout
- flex-basis: 30% per link adjustable
- justify-content: space-between for even distribution
- 5px margin for spacing

HTML: container div with link-container child holding link elements.
Each link gets flex-basis 30 percent and 5px margin, text-align center.

Auto-wraps links to next line when space runs out. Fully responsive.
