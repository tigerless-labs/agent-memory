---
name: all2trade-tech-stack-python-3-flask-mysql-ccxt-deep-learning-framework-celery
abstract: "All2Trade tech stack: Python 3, Flask, MySQL, CCXT, deep learning framework, Celery"
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

**Technology Stack**:
- Language: Python 3
- Web Framework: Flask (lightweight)
- Database: MySQL
- Exchange Integration: CCXT library
- Data Processing: Pandas
- Deep Learning: TensorFlow, PyTorch, or Keras
- Task Scheduling: Celery (for automated trading)
- Authentication: Flask-Login, Flask-JWT

**Architecture Flow**:
1. Users sign up/login via Flask web interface
2. Users submit opinions on currency trends
3. Deep learning model processes user opinions + market data → trend prediction
4. Automated system executes trades based on model predictions
5. Revenue generated from spreads; users receive percentage of profits
6. Model is periodically retrained with latest market data and actual outcomes

Deep learning handles both opinion aggregation and autonomous improvement over time.
