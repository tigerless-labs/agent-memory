---
name: all2trade-tech-stack-python-3-flask-mysql-with-ccxt-and-deep-learning
abstract: "All2Trade tech stack: Python 3, Flask, MySQL with CCXT and deep learning"
type: decision
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

**Technology Stack** chosen for All2Trade:

- **Language**: Python 3
- **Web Framework**: Flask (lightweight, good for minimal frontend)
- **Database**: MySQL
- **Market Data & Exchange Integration**: CCXT library
- **Data Processing**: Pandas
- **Task Scheduling**: Celery (for automated periodic tasks)
- **Authentication**: Flask-Login + Flask-JWT
- **Deep Learning Frameworks**: TensorFlow, PyTorch, or Keras (to be selected)

**Architecture Pattern**:
- Frontend: Flask-based web interface for opinion submission
- Backend: Python with business logic
- Database: MySQL stores users, opinions, trades, payouts
- Automation: Celery schedules market checks and trade execution
- ML: Deep learning model learns from historical data + user opinions, retrains periodically

**Integration Points**:
- CCXT for cryptocurrency exchange connections
- Scheduled tasks trigger trading logic and model retraining
- Model predictions combined with user opinions for trading decisions
