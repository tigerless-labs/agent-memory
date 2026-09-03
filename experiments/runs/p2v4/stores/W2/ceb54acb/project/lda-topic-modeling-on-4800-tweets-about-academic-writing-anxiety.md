---
name: lda-topic-modeling-on-4800-tweets-about-academic-writing-anxiety
abstract: LDA topic modeling on 4800 tweets about academic writing anxiety
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

Dataset: 4800 tweets, all containing 'academic writing anxiety', tokenized in DataFrame column 'tokens'. Preprocessing: (1) Created id2word dictionary using Gensim's Dictionary class; (2) Filtered extremes with no_below=100, no_above=0.7; (3) Created corpus using doc2bow. LDA Model: Gensim LdaMulticore with num_topics=3, passes=5, workers=2, random_state=42. Analysis: Extract top 10 words per topic from model.print_topics(), join into strings, obtain topic probability distributions using model.get_document_topics(corpus).
