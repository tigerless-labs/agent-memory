---
created: 2026-09-03T01:21:50.490117439Z
updated: 2026-09-03T01:21:50.490117439Z
weight: 1.0
last_accessed: 2026-09-03T01:21:50.490117439Z
access_count: 0
pinned: false
links:
- all2trade-database-schema
abstract: All2Trade cryptocurrency trading platform, May 2023; users submit trend predictions (free); system trades and pays users percentage of profits; Python 3, Flask, MySQL; automated trading with deep learning expansion
---

## All2Trade Project — Cryptocurrency Trading Platform

**Date:** May 21, 2023  
**Status:** Architecture designed

### Overview
All2Trade is an automated cryptocurrency trading platform that uses crowdsourced user opinions to make trading decisions.

### Business Model
- Users provide opinions on cryptocurrency trends through a simple web interface — **completely free for users**
- The platform executes automated trades based on aggregated user opinions
- Revenue generated from trades is split: users receive a small percentage of profits; platform keeps the difference

### Technology Stack
- **Language:** Python 3
- **Web Framework:** Flask
- **Database:** MySQL
- **Data Processing:** Pandas
- **Crypto Exchange Integration:** ccxt library
- **Task Scheduling:** Celery (for automated trading and retraining)
- **Authentication:** Flask-Login, Flask-JWT

### Core Workflow
1. Users sign up and authenticate
2. Users submit opinions on currency trend (up/down/neutral) via simple interface
3. System aggregates opinions + optional deep learning predictions
4. Automated trades executed based on aggregated signals
5. Revenue generated and distributed to contributing users
6. Model continuously retrained on latest data

### Deep Learning Expansion
- Input: user opinions + market data + other signals
- Output: trend prediction as probability distribution
- Frameworks considered: TensorFlow, PyTorch, Keras
- Periodic retraining via Celery scheduled tasks
- Model prediction combined with user opinions for final trading decisions