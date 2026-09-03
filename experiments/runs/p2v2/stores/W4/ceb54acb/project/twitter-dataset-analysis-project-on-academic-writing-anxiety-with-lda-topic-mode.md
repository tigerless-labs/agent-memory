---
name: twitter-dataset-analysis-project-on-academic-writing-anxiety-with-lda-topic-mode
abstract: Twitter dataset analysis project on academic writing anxiety with LDA topic modeling
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

Dataset: 4800 tweets containing keyword academic writing anxiety. Methodology: LDA-based topic modeling using Gensim library. Preprocessing: tokenization, dictionary creation (id2word), extreme filtering (no_below=100, no_above=0.7). Model: LdaMulticore with 3 topics, 5 passes, 2 workers, random_state=42. Tools: Gensim, spaCy, scikit-learn (CountVectorizer, LatentDirichletAllocation). Approach: Extract top 10 words per topic, analyze topic probabilities for each tweet using get_document_topics() method.
