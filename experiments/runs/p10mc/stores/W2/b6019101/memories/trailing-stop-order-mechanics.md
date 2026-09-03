---
created: 2026-09-02T23:27:30.321576180Z
updated: 2026-09-02T23:27:30.321576180Z
weight: 1.0
last_accessed: 2026-09-02T23:27:30.321576180Z
access_count: 0
pinned: false
links: []
abstract: Trailing stop order mechanics explained April 27 2023 with 10% example. $50 purchase, $55 high, $49.50 stop trigger. Adjusts with highs, not with declines.
---

## Trailing Stop Order Mechanics

A trailing stop order is a dynamic stop order that adjusts the stop price based on stock price movements.

### Example: 10% Trailing Stop

Starting position: Bought stock at $50, set trailing stop at 10%.

1. Stock rises to $55
   - Trailing stop adjusts to $49.50 ($55 minus 10% of $55)
   - Stop price moves up with the high

2. Stock rises to $60
   - Trailing stop adjusts to $54.00 ($60 minus 10% of $60)
   - Stop price continues upward

3. Stock falls from $55 to $53
   - Stop price remains at $49.50
   - It does NOT adjust downward - it only follows the peaks

### Key Benefits

- Protects against significant losses
- Allows for potential gains if stock continues rising
- Automatically adjusts - useful for investors who cannot constantly monitor
- Popular with traders wanting upside potential with downside protection

### Limitations

- Does not guarantee profits in volatile markets
- In fast-moving crashes, stock may gap down past stop price and not execute at desired price
- May trigger too early in high-volatility stocks with low volume
- Not suitable for all stocks (low-volume or high-volatility securities)