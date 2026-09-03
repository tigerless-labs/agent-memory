---
name: all2trade-cryptocurrency-trading-app-using-user-opinions-and-deep-learning
abstract: "All2Trade: cryptocurrency trading app using user opinions and deep learning"
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

## Project: All2Trade

**Purpose**: Automated system that uses condensed knowledge of user base to trade cryptocurrency and generate revenue.

**Technology Stack**:
- Python 3
- Flask (web framework)
- MySQL (database)
- Deep Learning framework (TensorFlow, PyTorch, or Keras)
- Pandas for data manipulation
- CCXT library for cryptocurrency exchange interaction
- Celery for scheduled tasks

**Users**: Everyone who wants to help the system make trading decisions in exchange for a percentage of revenues.

**Business Model**:
- Platform is completely free for users
- Users provide opinions on future trends of currencies through simple interface
- System generates revenue by trading using user opinions
- Users receive small percentage of payout
- Business keeps the difference

**Features**:
- Automated and minimal design
- User authentication (Flask-Login, Flask-JWT)
- Deep learning model that learns and evolves over time
- Model input: users' opinions + market data
- Model output: probability distribution of future trends
- Periodic model retraining using latest data

**Database Tables** (from 2023-05-21 discussion):
1. **Users**: id, username, password (hashed), email, first_name, last_name
2. **Opinions**: id, user_id (FK), currency, trend (up/down/neutral), timestamp
3. **Trades**: id, currency, trend, buy_price, sell_price, profit, timestamp
4. **Payouts**: id, user_id (FK), amount, timestamp

**Workflow**:
1. Users sign up and log in
2. Users provide opinions on currency trends
3. Deep learning model processes opinions + market data
4. System makes trades based on user opinions + model prediction
5. Revenue generated and percentage paid to contributing users
6. Model periodically retrained to improve accuracy
