---
name: lda-topic-modeling-on-twitter-dataset-using-gensim
abstract: LDA topic modeling on Twitter dataset using Gensim
type: procedure
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

Applied LDA-based topic modeling to academic writing anxiety tweets using Gensim (LdaMulticore). Configuration:
- Number of topics: 3
- Passes: 5
- Random state: 42
- Workers: 2
- Dictionary filtering: no_below=100, no_above=0.7
- Extracted top 10 words per topic
- Obtained document-topic probabilities using get_document_topics()
