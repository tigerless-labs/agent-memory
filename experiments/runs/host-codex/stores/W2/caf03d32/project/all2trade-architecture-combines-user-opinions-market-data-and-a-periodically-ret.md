---
name: all2trade-architecture-combines-user-opinions-market-data-and-a-periodically-ret
abstract: "All2Trade architecture combines user opinions, market data, and a periodically retrained deep learning prediction"
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

Recommended architecture: Flask frontend/API; MySQL storage; Python backend using Pandas and ccxt; Flask-Login and Flask-JWT for authentication and authorization; scheduled tasks or Celery for market fetching, trading, and model retraining. The deep learning model should take user opinions, market data, and other relevant inputs and output a probability distribution over future trends. Candidate frameworks: TensorFlow, PyTorch, or Keras. Its prediction is combined with user opinions for automated trading and periodically retrained on the latest data.
