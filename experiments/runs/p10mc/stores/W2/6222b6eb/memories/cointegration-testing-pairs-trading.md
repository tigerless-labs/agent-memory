---
created: 2026-09-02T23:43:31.798119550Z
updated: 2026-09-02T23:43:31.798119550Z
weight: 1.0
last_accessed: 2026-09-02T23:43:31.798119550Z
access_count: 0
pinned: false
links:
- statistical-arbitrage-course-framework-python
abstract: Cointegration measures long-term equilibrium relationship between non-stationary time series; pairs trading strategy; statsmodels coint function; p-value less than 0.05 indicates cointegration; spread reversion-based profits
---

## Cointegration and Pairs Trading

**Definition:** Long-term equilibrium relationship between two or more non-stationary time series. Assets move together over time.

**Key Difference from Correlation:**
- Correlation: Linear relationship over specific time period, -1 to 1
- Cointegration: Long-term equilibrium, stationary relationship
- Can have high correlation but no cointegration, or vice versa

**Python Testing with statsmodels:**
```python
from statsmodels.tsa.stattools import coint

p_value = coint(data1['Price'], data2['Price'])[1]

if p_value < 0.05:
    print('Cointegrated')
else:
    print('Not cointegrated')
```

**Trading Strategy:**
- Identify cointegrated pairs
- Trade the spread between them
- Profit when spread reverts to long-term relationship
- Strategy depends on pair characteristics and risk tolerance