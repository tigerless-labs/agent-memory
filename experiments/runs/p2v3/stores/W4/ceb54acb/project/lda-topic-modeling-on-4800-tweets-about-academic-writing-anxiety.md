---
name: lda-topic-modeling-on-4800-tweets-about-academic-writing-anxiety
abstract: LDA topic modeling on 4800 tweets about academic writing anxiety
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-22
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Applied Gensim LDA-based topic modeling to a dataset of 4800 tweets containing the keyword "academic writing anxiety".

## Methodology
- **Model**: LdaMulticore (Gensim)
- **Topics**: 3
- **Dictionary filtering**: no_below=100, no_above=0.7 (words appearing in <100 tweets or >70% of tweets removed)
- **Parameters**: 5 passes, random_state=42, 2 workers
- **Analysis**: Extracted top 10 words per topic and obtained document topic probabilities for each tweet

## Purpose
Extract and identify relevant topics discussed in tweets about academic writing anxiety.
