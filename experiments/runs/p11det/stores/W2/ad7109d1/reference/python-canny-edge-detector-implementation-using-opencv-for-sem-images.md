---
name: python-canny-edge-detector-implementation-using-opencv-for-sem-images
abstract: Python Canny edge detector implementation using OpenCV for SEM images
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Complete Python implementation of Canny edge detection using OpenCV library for detecting material boundaries in SEM images. Implementation includes:

- Gaussian blur for noise reduction
- Sobel operators for gradient calculation (X and Y directions)
- Gradient magnitude and direction computation
- Non-maximum suppression to thin edges (8-directional checks)
- Double thresholding to identify strong and weak edges
- Edge tracing with hysteresis to connect edges

Function signature: `detect_edges(image, low_threshold, high_threshold)`

Returns binary image with detected edges as 255 (white) on black background.

Original file processed: sem.jpeg
