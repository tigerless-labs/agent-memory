---
created: 2026-09-03T01:21:55.527792376Z
updated: 2026-09-03T01:21:55.527792376Z
weight: 1.0
last_accessed: 2026-09-03T01:21:55.527792376Z
access_count: 0
pinned: false
links:
- all2trade-cryptocurrency-platform
abstract: All2Trade MySQL database schema; tables for Users, Opinions, Trades, Payouts; May 2023
---

## All2Trade Database Schema

### Users Table
```
id (PK, auto-increment)
username (unique)
password (hashed)
email
first_name
last_name
```

### Opinions Table
Records each user opinion on cryptocurrency trends
```
id (PK, auto-increment)
user_id (FK → Users.id)
currency (e.g., Bitcoin, Ethereum)
trend (enum: "up", "down", "neutral")
timestamp (when opinion was submitted)
```

### Trades Table
Records all trades executed by the system
```
id (PK, auto-increment)
currency (traded currency)
trend (enum: "up", "down", "neutral" — aggregated from opinions/model)
buy_price (entry price)
sell_price (exit price)
profit (amount gained from trade)
timestamp (when trade was executed)
```

### Payouts Table
Tracks revenue distribution to users
```
id (PK, auto-increment)
user_id (FK → Users.id)
amount (payout in USD or other currency)
timestamp (when payout was issued)
```

### Future Considerations
- May need to track which opinions contributed to which trades (many-to-many relationship)
- May need model prediction scores/confidence table if persisting model outputs
- May need trade attribution table to link user opinions to specific trades and resulting payouts