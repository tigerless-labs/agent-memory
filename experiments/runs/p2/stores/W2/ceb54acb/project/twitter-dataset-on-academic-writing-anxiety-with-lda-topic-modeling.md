---
name: twitter-dataset-on-academic-writing-anxiety-with-lda-topic-modeling
abstract: Twitter dataset on academic writing anxiety with LDA topic modeling
type: fact
status: active
created: 2026-09-01
updated: 2026-09-01
valid_from: 2026-09-01
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Dataset: 4800 tweets with keyword 'academic writing anxiety'. Applying LDA (Latent Dirichlet Allocation) topic modeling via Gensim library.

Process:
- Tokenization and cleaning of tweets
- Dictionary creation (id2word) from tokens
- Filtering extremes: no_below=100, no_above=0.7
- Corpus creation with bag-of-words representation
- LdaMulticore model with 3 topics, 5 passes, random_state=42
- Extracting top 10 words per topic
- Obtaining topic probabilities for each tweet

Stack: Python, Gensim, scikit-learn
