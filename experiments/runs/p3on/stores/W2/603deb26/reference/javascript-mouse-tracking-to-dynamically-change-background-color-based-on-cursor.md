---
name: javascript-mouse-tracking-to-dynamically-change-background-color-based-on-cursor
abstract: "JavaScript: mouse tracking to dynamically change background color based on cursor position"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-08-11
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Example code to track mouse movement and change background color in real-time.

HTML:
```html
<!DOCTYPE html>
<html>
<head>
  <title>Mouse Tracking</title>
</head>
<body onmousemove="trackMouse(event)">
  <h1>Move your mouse to change the background color</h1>
  <p>Mouse position: <span id="mousePosition"></span></p>
  <script src="script.js"></script>
</body>
</html>
```

JavaScript:
```javascript
function trackMouse(event) {
  var x = event.clientX;
  var y = event.clientY;
  
  document.getElementById("mousePosition").innerHTML = x + ", " + y;
  
  var red = x % 256;
  var green = y % 256;
  var blue = (x + y) % 256;
  document.body.style.backgroundColor = "rgb(" + red + ", " + green + ", " + blue + ")";
}
```

The function tracks mouse position via event.clientX and event.clientY, updates display, and calculates RGB color values using modulo operator to keep values in 0-255 range.
