---
created: 2026-09-02T23:43:27.496400429Z
updated: 2026-09-02T23:43:27.496400429Z
weight: 1.0
last_accessed: 2026-09-02T23:43:27.496400429Z
access_count: 0
pinned: false
links:
- statistical-arbitrage-course-framework-python
abstract: Mean reversion trading strategy using z-score; price reverts to long-term average; z-score measures standard deviations from mean; Python code with rolling window (lookback 30 days); threshold-based entry/exit signals
---

## Mean Reversion Strategy with Z-Score

**Concept:** Financial instruments revert to long-term average price; not purely random movement.

**Z-Score:** Measures number of standard deviations from mean dataset.

**Python Implementation:**
```python
import pandas as pd
import numpy as np

lookback = 30
mean = data["Price"].rolling(window=lookback).mean()
std = data["Price"].rolling(window=lookback).std()
data["Z-Score"] = (data["Price"] - mean) / std
```

**Trading Logic:**
- High z-score threshold → short (expect revert downward)
- Low z-score threshold → long (expect revert upward)
- Specific thresholds depend on strategy and risk tolerance