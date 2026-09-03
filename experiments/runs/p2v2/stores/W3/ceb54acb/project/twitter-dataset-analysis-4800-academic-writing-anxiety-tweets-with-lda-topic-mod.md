---
name: twitter-dataset-analysis-4800-academic-writing-anxiety-tweets-with-lda-topic-mod
abstract: "Twitter dataset analysis: 4800 academic writing anxiety tweets with LDA topic modeling"
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

**Dataset:** 4,800 tweets containing 'academic writing anxiety' keyword. **Tool:** Gensim LDA (Latent Dirichlet Allocation) topic modeling with LdaMulticore. **Preprocessing:** Dictionary filtering with min_doc_frequency=100, max_doc_freq=0.7. **Model params:** 3 topics, 5 passes, random_state=42, 2 workers. **Output:** Top 10 words per topic extracted via regex, topic probability distribution calculated per document. **Platform:** Jupyter notebooks.
