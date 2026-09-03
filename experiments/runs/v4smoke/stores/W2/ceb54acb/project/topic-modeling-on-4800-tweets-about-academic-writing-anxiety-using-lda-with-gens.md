---
name: topic-modeling-on-4800-tweets-about-academic-writing-anxiety-using-lda-with-gens
abstract: Topic modeling on 4800 tweets about academic writing anxiety using LDA with Gensim
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Dataset
- 4800 tweets
- All containing keyword: 'academic writing anxiety'
- Tokenized and cleaned

## Methodology: LDA Topic Modeling with Gensim

### Preprocessing
- Created id2word dictionary from tokenized tweets using gensim.corpora.Dictionary
- Filtered extremes: no_below=100 (minimum frequency), no_above=0.7 (document frequency cutoff)

### Model Configuration
- Algorithm: LdaMulticore (gensim.models.LdaMulticore)
- num_topics: 3
- passes: 5
- workers: 2
- random_state: 42

### Analysis Steps
1. Created corpus using doc2bow representation
2. Extracted top 10 words per topic using print_topics()
3. Generated topic summaries by joining top words
4. Obtained topic probabilities for each tweet using get_document_topics()

## Output
Topic labels and probability distributions for each tweet in the dataset.
