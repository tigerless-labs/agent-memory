---
name: cryptocurrency-trading-system-project-all2trade-python-flask-mysql-with-deep-lea
abstract: "Cryptocurrency trading system project (All2Trade): Python/Flask/MySQL with deep learning"
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

User interested in building an automated cryptocurrency trading system named All2Trade that uses crowdsourced user opinions.

**Core concept:**
- Users provide opinions on currency trends through a simple interface
- System makes trades based on aggregated user opinions + ML model predictions
- Revenue generated from trades; users receive percentage payout
- Platform free for users

**Technology stack:**
- Python 3
- Flask (web framework)
- MySQL (database)
- Deep learning frameworks: TensorFlow, PyTorch, or Keras
- Data processing: Pandas
- Crypto exchange integration: CCXT library
- Task automation: Celery

**System components:**
- User authentication (Flask-Login, Flask-JWT)
- Opinion collection interface
- Automated trading engine (scheduled tasks/message queue)
- Deep learning model that learns from market data and user opinions over time
- Periodic model retraining for continuous improvement

**Database schema:**
- Users table (id, username, password, email, first_name, last_name)
- Opinions table (id, user_id, currency, trend, timestamp)
- Trades table (id, currency, trend, buy_price, sell_price, profit, timestamp)
- Payouts table (id, user_id, amount, timestamp)
