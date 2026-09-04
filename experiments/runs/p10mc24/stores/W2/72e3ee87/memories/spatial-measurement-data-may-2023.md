---
created: 2026-09-02T21:25:32.104467743Z
updated: 2026-09-02T21:25:32.104467743Z
weight: 1.0
last_accessed: 2026-09-02T21:25:32.104467743Z
access_count: 0
pinned: false
links: []
abstract: May 4, 2023 — measurement dataset with X [m], Y [m], Wert [nT] columns; 81 rows; X -0.463 to -0.480, Y 22.455 to 27.190, Wert -32.160 to 115.670; loaded to pandas DataFrame
---

## Dataset

**Session:** 2023-05-04 (Thursday) 12:03

**Columns:**
- X [m]: spatial coordinate, range -0.463 to -0.480 m
- Y [m]: spatial coordinate, range 22.455 to 27.190 m
- Wert [nT]: magnetic field or related measurement, range -32.160 to 115.670 nanoTesla

**Total rows:** 81

**Solution provided:** Load with pandas:
```python
import pandas as pd

df = pd.DataFrame(data, columns=["X", "Y", "Wert"])
```

Data contains regular spatial sampling with corresponding Wert measurements. Peak Wert value is 115.670 nT at approximately X=-0.446 m, Y=23.397 m.