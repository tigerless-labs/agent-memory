---
name: twitter-dataset-4800-tweets-on-academic-writing-anxiety-analyzed-with-lda-topic
abstract: "Twitter dataset: 4800 tweets on academic writing anxiety analyzed with LDA topic modeling"
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

Dataset: 4800 tweets with keyword 'academic writing anxiety' from Twitter.

LDA Topic Modeling (Gensim):
- id2word Dictionary from tokenized tweets
- Filtered extremes: no_below=100, no_above=0.7
- Corpus built with doc2bow()
- LdaMulticore: 3 topics, workers=2, passes=5, random_state=42
- Extracted top 10 words per topic
- Generated topic labels and document-topic probabilities for each tweet
