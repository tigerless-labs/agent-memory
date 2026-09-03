---
name: edge-detection-algorithms-for-image-processing-canny-sobel-log-thresholding
abstract: "Edge detection algorithms for image processing: Canny, Sobel, LoG, thresholding"
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

Common edge detection algorithms used in image processing:

**Canny Edge Detector** - Popular multi-step algorithm:
1. Gaussian blur to reduce noise
2. Sobel operator for gradient calculation
3. Non-maximum suppression
4. Double thresholding
5. Edge tracing with hysteresis

**Sobel Operator** - Gradient-based edge detection using 3x3 kernels

**Laplacian of Gaussian (LoG)** - Second derivative approach

**Thresholding** - Simple intensity-based region separation

**Applications:** Material characterization in SEM images, general edge detection, boundary detection

**Python implementation:** OpenCV library provides built-in functions and manual implementations possible with NumPy
