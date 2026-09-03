---
name: all2trade-expansion-integrate-deep-learning-system-for-opinion-prediction
abstract: "All2Trade expansion: integrate deep learning system for opinion prediction"
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

## Decision: Add deep learning layer to All2Trade\n\n**Approach**:\n1. Input: combination of user opinions, market data, and other relevant signals\n2. Output: probability distribution over trend predictions (up/down/neutral)\n3. ML framework: TensorFlow, PyTorch, or Keras\n4. Integration: new backend endpoint to accept input and return model predictions\n5. Model improves over time: periodic retraining with latest market data via Celery\n\n**Revised workflow**:\n- Users provide opinions on currency trends\n- Deep learning model processes opinions + market data\n- System combines user predictions + model output for trading decisions\n- Model retrains periodically to improve accuracy\n- Revenue split: users paid percentage, platform keeps difference\n\n**Benefit**: ML predictions should improve overall quality of trading decisions.
