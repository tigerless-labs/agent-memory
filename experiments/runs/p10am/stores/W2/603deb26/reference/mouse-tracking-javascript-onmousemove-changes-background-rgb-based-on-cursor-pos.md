---
name: mouse-tracking-javascript-onmousemove-changes-background-rgb-based-on-cursor-pos
abstract: "Mouse tracking JavaScript: onmousemove changes background RGB based on cursor position"
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

HTML: <body onmousemove=trackMouse(event)>

JavaScript:
- Get x = event.clientX, y = event.clientY
- Calculate red = x % 256, green = y % 256, blue = (x+y) % 256
- Set document.body.style.backgroundColor with rgb values
