---
name: mean-reversion-and-z-score-trading-identifying-price-reversions-using-standard-d
abstract: "Mean reversion and z-score trading: identifying price reversions using standard deviations"
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

Mean reversion strategy assumes prices eventually revert to their long-term average.\n\nZ-Score approach:\n- Z-score = (price - mean) / standard deviation\n- Measures how many standard deviations a price is from its mean\n- Implementation: compute rolling mean and std over lookback period (e.g., 30 days)\n- When z-score moves far from zero (above/below threshold), likely to revert\n- Trading signals: short when z-score is high, long when z-score is low\n- Specific thresholds depend on trading strategy and risk tolerance\n\nPython implementation uses Pandas rolling averages and NumPy std calculations
