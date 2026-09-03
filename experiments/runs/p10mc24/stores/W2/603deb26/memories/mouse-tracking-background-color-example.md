---
created: 2026-09-02T21:25:34.109176508Z
updated: 2026-09-02T21:25:34.109176508Z
weight: 1.0
last_accessed: 2026-09-02T21:25:34.109176508Z
access_count: 0
pinned: false
links: []
abstract: Practical example using onmousemove event to track mouse coordinates and dynamically change HTML body background color using rgb() values derived from clientX, clientY position modulo 256
---

## Mouse Tracking with Dynamic Background Color

**Implementation Pattern**

Uses `onmousemove` event attached to `<body>` to track mouse position and change background color in real-time.

**HTML Structure**
```html
<body onmousemove="trackMouse(event)">
  <h1>Move your mouse to change the background color</h1>
  <p>Mouse position: <span id="mousePosition"></span></p>
  <script src="script.js"></script>
</body>
```

**JavaScript Function**
```javascript
function trackMouse(event) {
  // Get current mouse position
  var x = event.clientX;
  var y = event.clientY;
  
  // Update display element
  document.getElementById("mousePosition").innerHTML = x + ", " + y;
  
  // Calculate RGB values from position (modulo 256 keeps values 0-255)
  var red = x % 256;
  var green = y % 256;
  var blue = (x + y) % 256;
  
  // Apply background color
  document.body.style.backgroundColor = "rgb(" + red + ", " + green + ", " + blue + ")";
}
```

**Key Techniques**
- `event.clientX` and `event.clientY` — get current mouse coordinates
- Modulo operator (%) — constrain RGB values to 0-255 range
- `document.body.style.backgroundColor` — modify CSS inline style dynamically
- `rgb()` function — set color with calculated values