---
created: 2026-09-03T01:28:46.327624753Z
updated: 2026-09-03T01:28:46.327624753Z
weight: 1.0
last_accessed: 2026-09-03T01:28:46.327624753Z
access_count: 0
pinned: false
links:
- SEM edge detection interest
abstract: May 21, 2023 — Python code for Canny edge detection using OpenCV; implements Gaussian blur, gradient calculation, non-maximum suppression, double thresholding, edge tracing
---

Complete Python implementation of Canny edge detection algorithm provided on May 21, 2023:

**Key steps implemented:**
1. Gaussian filter (3×3 kernel) to reduce noise
2. Sobel operator to calculate gradient magnitude and direction
3. Non-maximum suppression to thin edges
4. Double thresholding to identify strong/weak edges
5. Edge tracing with hysteresis to connect edges

**Function signature:**
```python
def detect_edges(image, low_threshold, high_threshold):
```

Uses NumPy for numerical operations and OpenCV (cv2) for image processing. Returns binary image (uint8) with edges marked as 255.

Input: grayscale image and two threshold values
Output: binary edge image

Code was incomplete at end of conversation (being continued).