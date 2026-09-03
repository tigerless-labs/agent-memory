---
name: techniques-for-handling-high-cardinality-categorical-variables-in-feature-engine
abstract: Techniques for handling high cardinality categorical variables in feature engineering
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-29
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Techniques for high cardinality categorical variables: (1) Grouping/binning - group categories by business knowledge or clustering; (2) Hash encoding - use FeatureHasher to convert to numerical; (3) One-hot encoding with SelectKBest - OHE then select top K features; (4) Embeddings - word2vec or TensorFlow embeddings for dense vectors; (5) Target encoding - replace categories with mean/median of target variable; (6) Feature extraction - extract frequency, average order value, time since last purchase; (7) Dimensionality reduction - PCA, t-SNE, UMAP after encoding. Models that handle high cardinality well: Random Forests (feature importance), Gradient Boosting Machines (feature importance), Neural Networks (with embeddings or OHE).
