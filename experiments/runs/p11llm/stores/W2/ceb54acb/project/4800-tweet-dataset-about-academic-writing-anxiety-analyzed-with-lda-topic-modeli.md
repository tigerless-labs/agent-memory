---
name: 4800-tweet-dataset-about-academic-writing-anxiety-analyzed-with-lda-topic-modeli
abstract: 4800-tweet dataset about academic writing anxiety analyzed with LDA topic modeling
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

Dataset: 4800 tweets containing 'academic writing anxiety' keyword

LDA Model (Gensim LdaMulticore):
- Topics: 3
- Passes: 5  
- Workers: 2
- Random state: 42

Processing: id2word Dictionary > filter extremes (no_below=100, no_above=0.7) > doc2bow corpus > LDA model > extract top 10 words per topic > topic probabilities

Libraries: Gensim, spaCy, scikit-learn, pandas

Research: Computational social science on Twitter community patterns around academic writing anxiety
