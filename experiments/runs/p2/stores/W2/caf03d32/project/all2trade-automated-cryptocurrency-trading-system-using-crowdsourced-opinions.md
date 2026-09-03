---
name: all2trade-automated-cryptocurrency-trading-system-using-crowdsourced-opinions
abstract: "All2Trade: automated cryptocurrency trading system using crowdsourced opinions"
type: fact
status: active
created: 2026-09-01
updated: 2026-09-01
valid_from: 2026-09-01
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

**Project:** All2Trade cryptocurrency trading platform

**Purpose:** Automated system that aggregates user opinions on crypto trends to execute profitable trades and share revenues with contributors.

**Technology stack:**
- Python 3 (backend)
- Flask (web framework)
- MySQL (database)
- Deep learning integration (planned for improved predictions)

**Business model:**
- Users provide opinions on currency trend predictions (free)
- System makes automated trades based aggregated opinions + ML predictions
- Revenue generated from successful trades
- Users paid small percentage of payout from trades they influenced
- Platform retains difference as profit

**Database structure:**
- Users table (id, username, password, email, first/last name)
- Opinions table (id, user_id, currency, trend, timestamp)
- Trades table (id, currency, trend, buy_price, sell_price, profit, timestamp)
- Payouts table (id, user_id, amount, timestamp)

**Deep learning integration (in planning):**
- Input: user opinions + market data
- Output: probability distribution over trend predictions
- Framework: TensorFlow/PyTorch/Keras (to be chosen)
- Model retraining: periodic updates with latest data via scheduled tasks/Celery
- Goal: improve prediction accuracy over time
