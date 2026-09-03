---
name: all2trade-crowdsourced-cryptocurrency-trading-system-with-deep-learning
abstract: "All2Trade: Crowdsourced cryptocurrency trading system with deep learning"
type: fact
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

Project: All2Trade (started 2023-05-21)

Purpose: Automated system using aggregated user opinions to trade cryptocurrency and generate revenue.

Tech stack: Python 3, Flask, MySQL

Core business model:
- Platform free for users
- Revenue: profit from trades based on user opinions
- Users receive small percentage of payouts

Features (planned/discussed):
- User authentication (Flask-Login, Flask-JWT)
- Opinion interface: users predict currency trend (up/down/neutral)
- Automated trading via scheduled tasks/Celery
- Integration with crypto exchanges (ccxt library)
- Deep learning component for model predictions (TensorFlow/PyTorch/Keras)
- Periodic model retraining to improve accuracy

Database tables designed:
- Users (id, username, password hash, email, name)
- Opinions (id, user_id, currency, trend, timestamp)
- Trades (id, currency, trend, buy_price, sell_price, profit, timestamp)
- Payouts (id, user_id, amount, timestamp)

Deep learning workflow: Model takes user opinions + market data as input, outputs trend prediction (probability distribution). Results combined with user opinions for trading decisions.
