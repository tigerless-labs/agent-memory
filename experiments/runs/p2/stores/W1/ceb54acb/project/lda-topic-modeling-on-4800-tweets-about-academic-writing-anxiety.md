---
name: lda-topic-modeling-on-4800-tweets-about-academic-writing-anxiety
abstract: LDA topic modeling on 4800 tweets about academic writing anxiety
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

**Dataset:**
- 4,800 tweets
- Keyword filter: 'academic writing anxiety'
- Source: Twitter

**Methods:**
- Topic modeling approach: LDA (Latent Dirichlet Allocation)
- Library: Gensim (LdaMulticore)
- Number of topics: 3
- Model parameters:
  - Passes: 5
  - Workers: 2
  - Random state: 42

**Preprocessing pipeline:**
- Tokenization stored in 'tokens' column
- Dictionary creation with id2word
- Filtering extremes: no_below=100, no_above=0.7
- Corpus creation via doc2bow

**Outputs:**
- Extracts top 10 words per topic
- Generates topic probabilities for each tweet via get_document_topics()
- Displays topics with id labels

**Research focus:** Computational social science, Twitter analysis, topic extraction
