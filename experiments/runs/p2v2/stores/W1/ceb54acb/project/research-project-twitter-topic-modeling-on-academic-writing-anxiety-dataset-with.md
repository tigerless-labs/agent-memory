---
name: research-project-twitter-topic-modeling-on-academic-writing-anxiety-dataset-with
abstract: "Research project: Twitter topic modeling on 'academic writing anxiety' dataset with 4800 tweets using LDA-based approach"
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

Dataset: 4800 tweets containing keyword 'academic writing anxiety'. Using LDA-based topic modeling (LdaMulticore from Gensim) to extract topics. Process includes:
- Tokenization and cleaning
- id2word dictionary creation
- Filtering extremes (no_below=100, no_above=0.7)
- Corpus creation (doc2bow)
- LDA model instantiation (3 topics, 5 passes, random_state=42)
- Topic extraction and probability analysis

Research focuses on computational social science with Twitter data and topic modeling.
