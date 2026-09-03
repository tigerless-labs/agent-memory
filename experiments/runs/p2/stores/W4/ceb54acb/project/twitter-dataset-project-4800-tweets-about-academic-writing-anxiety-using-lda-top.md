---
name: twitter-dataset-project-4800-tweets-about-academic-writing-anxiety-using-lda-top
abstract: "Twitter dataset project: 4800 tweets about academic writing anxiety; using LDA topic modeling with Gensim"
type: fact
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

**Project:** Computational social science research on Twitter data

**Dataset:**
- 4800 tweets containing keyword 'academic writing anxiety'
- Text preprocessing includes tokenization and cleaning

**Methods:**
- Topic modeling using LDA (Latent Dirichlet Allocation)
- Libraries: Gensim (Dictionary, LdaMulticore), scikit-learn
- Parameters: 
  - 3 topics extracted
  - 5 passes for LDA model
  - Filter extremes: no_below=100, no_above=0.7
  - workers=2, random_state=42

**Analysis pipeline:**
1. Create id2word dictionary from tokenized tweets
2. Filter extremes to remove rare/common words
3. Create corpus using doc2bow
4. Instantiate LdaMulticore model
5. Extract and display top topics
6. Obtain topic probabilities for each tweet

**Expert area:** Computational social science with research focus on Twitter and topic modeling
