---
name: cointegration-vs-correlation-distinguishing-long-term-relationships-from-short-t
abstract: "Cointegration vs correlation: distinguishing long-term relationships from short-term linear association"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Two fundamental concepts in pairs trading:\n\nCorrelation:\n- Measures linear relationship between two instruments over a specific period\n- Range: -1 (perfect negative) to +1 (perfect positive), 0 = no correlation\n- Short-term measure; doesn't imply long-term movement together\n\nCointegration:\n- Measures long-term equilibrium relationship between non-stationary time series\n- Two instruments can deviate short-term but revert to long-term relationship\n- Tested using statsmodels.tsa.stattools.coint() function\n- P-value < 0.05 typically indicates statistically significant cointegration\n- Suitable for identifying pairs trading opportunities\n\nKey insight: Two instruments can be cointegrated without high correlation, and highly correlated instruments may not be cointegrated. For statistical arbitrage, cointegration is more useful than correlation alone.
