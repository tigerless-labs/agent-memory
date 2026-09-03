---
created: 2026-09-02T23:43:42.493447484Z
updated: 2026-09-02T23:43:42.493447484Z
weight: 1.0
last_accessed: 2026-09-02T23:43:42.493447484Z
access_count: 0
pinned: false
links: []
abstract: Correlation vs Cointegration - correlation measures linear relationship -1 to 1 over time period; cointegration measures long-term equilibrium between non-stationary time series; both can be computed using Python numpy and statsmodels
---

## Correlation vs Cointegration

**Correlation:**
- Measures linear relationship between two financial instruments
- Ranges from -1 (perfect negative) to 0 (no relationship) to 1 (perfect positive)
- Time-period specific
- Python: `np.corrcoef(data1, data2)[0, 1]`

**Cointegration:**
- Measures long-term equilibrium relationship between time series
- Implies assets move together in the long run
- Suitable for pairs trading strategies
- Python: `from statsmodels.tsa.stattools import coint; coint(data1, data2)`

**Key Distinction:**
- Two assets can be highly correlated but not cointegrated
- Two assets can have low correlation but be cointegrated
- Cointegration is more useful for long-term trading strategies
- Correlation is useful for any association measurement

**Practical Example:**
High correlation might exist over a month, but assets diverge long-term (not cointegrated).
Low correlation overall, but over decades they move together (cointegrated).