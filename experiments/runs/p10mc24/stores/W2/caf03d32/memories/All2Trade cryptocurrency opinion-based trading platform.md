---
created: 2026-09-02T21:33:32.758748998Z
updated: 2026-09-02T21:33:32.758748998Z
weight: 1.0
last_accessed: 2026-09-02T21:33:32.758748998Z
access_count: 0
pinned: false
links: []
abstract: May 21, 2023 — All2Trade cryptocurrency trading system combining crowdsourced user opinions with deep learning; Python 3, Flask, MySQL; free for users, revenue from trades, users paid percentage of profit
---

## Project Overview

**Name**: All2Trade

**Concept**: Automated cryptocurrency trading system using consensus user opinions + deep learning model that learns over time.

**Business Model**:
- Platform free for users
- Users submit opinions on currency trends (up/down/neutral)
- System trades based on combined user opinions + ML predictions
- Revenue from trade profits; pay users percentage of payout, keep difference

**Tech Stack**:
- Backend: Python 3, Flask
- Database: MySQL
- ML: TensorFlow/PyTorch/Keras (to be chosen)
- Libraries: Pandas (data manipulation), ccxt (crypto exchange API), Celery (scheduled tasks)
- Auth: Flask-Login, Flask-JWT

## Architecture

**Workflow**:
1. Users sign up, log in
2. Users submit opinions on specific currencies (simple interface)
3. Deep learning model processes opinions + market data → prediction
4. System combines user opinions + model prediction → trading decision
5. Trades executed automatically
6. Revenue split: users get percentage, platform keeps difference
7. Model periodically retrained on latest data

**Core Components**:
- Frontend: Flask web interface for opinion submission
- Backend: Python business logic (trading, payouts, auth)
- ML Pipeline: Deep learning model for trend prediction
- Automation: Celery for scheduled tasks (market data fetch, trading, model retraining)
- Authentication: Flask-Login + Flask-JWT

## Database Schema

**Users**:
- id (PK, auto-increment)
- username (unique)
- password (hashed)
- email
- first_name, last_name

**Opinions**:
- id (PK, auto-increment)
- user_id (FK to Users)
- currency
- trend (up/down/neutral)
- timestamp

**Trades**:
- id (PK, auto-increment)
- currency
- trend (system's predicted trend)
- buy_price
- sell_price
- profit
- timestamp

**Payouts**:
- id (PK, auto-increment)
- user_id (FK to Users)
- amount
- timestamp

## ML Model Integration

**Input**: User opinions + market data (OHLCV, technical indicators)  
**Output**: Trend prediction (probability distribution)  
**Framework**: TensorFlow/PyTorch/Keras (decision pending)  
**Retraining**: Periodic automated retraining via Celery to improve accuracy