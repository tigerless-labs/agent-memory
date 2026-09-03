---
name: canny-edge-detector-python-opencv-implementation-with-gaussian-blur-gradient-sup
abstract: "Canny edge detector: Python OpenCV implementation with Gaussian blur, gradient, suppression, and hysteresis"
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

Canny edge detector algorithm steps:\n1. Apply Gaussian filter (blur) to reduce noise\n2. Calculate gradient magnitude and direction using Sobel operator\n3. Non-maximum suppression to thin edges\n4. Double thresholding to identify strong and weak edges\n5. Edge tracing and hysteresis to connect strong edges\n\nPython implementation uses OpenCV (cv2) library. Takes image and two threshold values (low_threshold, high_threshold) as inputs. Returns binary image with detected edges.
