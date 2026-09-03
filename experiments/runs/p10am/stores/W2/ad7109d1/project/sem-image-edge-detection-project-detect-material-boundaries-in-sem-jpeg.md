---
name: sem-image-edge-detection-project-detect-material-boundaries-in-sem-jpeg
abstract: SEM image edge detection project - detect material boundaries in sem.jpeg
type: fact
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

Project to analyze Scanning Electron Microscopy (SEM) images and detect edges/boundaries of different materials.

**Image file:** sem.jpeg

**Goal:** Detect edges between different materials in SEM images

**Methods discussed:**
- Canny edge detector (preferred, implemented in Python)
- Sobel operator
- Laplacian of Gaussian (LoG)
- Thresholding
- Machine learning approaches

**Implementation approach:**
Using Python with OpenCV library. Canny edge detector steps:
1. Gaussian filter to reduce noise
2. Gradient magnitude and direction calculation
3. Non-maximum suppression to thin edges
4. Double thresholding for strong/weak edges
5. Edge tracing and hysteresis

**Status:** Partial Canny edge detector code written; needs completion to read sem.jpeg and apply edge detection
