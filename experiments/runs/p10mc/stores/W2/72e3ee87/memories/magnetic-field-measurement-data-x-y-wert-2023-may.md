---
created: 2026-09-02T23:25:01.839048460Z
updated: 2026-09-02T23:25:01.839048460Z
weight: 1.0
last_accessed: 2026-09-02T23:25:01.839048460Z
access_count: 0
pinned: false
links: []
abstract: May 4 2023 — 80-row magnetic field measurement dataset with X [m], Y [m], Wert [nT]; X range -0.463 to -0.480, Y range 22.455 to 27.190, Wert range -32.160 to 115.670 nanoTesla; loaded into pandas dataframe
---

## Dataset

- **Session:** May 4, 2023, 12:03 UTC
- **Format:** 80 rows of three columns
- **Columns:**
  - X [m]: X coordinate in meters, range -0.463 to -0.480
  - Y [m]: Y coordinate in meters, range 22.455 to 27.190
  - Wert [nT]: Magnetic field measurement in nanoTesla, range -32.160 to 115.670

## Peak observations

- Maximum Wert: 115.670 nT at Y ≈ 23.397
- Minimum Wert: -32.160 nT at Y ≈ 22.523

## Solution: Load into pandas

```python
import pandas as pd

data = [
    # 80 rows of [X, Y, Wert] arrays
]
df = pd.DataFrame(data, columns=['X [m]', 'Y [m]', 'Wert [nT]'])
```

**Note:** Full data rows provided in original conversation; this captures the column structure and value ranges.