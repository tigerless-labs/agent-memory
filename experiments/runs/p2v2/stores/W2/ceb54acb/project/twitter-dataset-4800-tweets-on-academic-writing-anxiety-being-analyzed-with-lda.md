---
name: twitter-dataset-4800-tweets-on-academic-writing-anxiety-being-analyzed-with-lda
abstract: "Twitter dataset: 4800 tweets on 'academic writing anxiety' being analyzed with LDA topic modeling"
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

Dataset contains 4800 tweets, all containing the keyword 'academic writing anxiety'. Applying LDA (Latent Dirichlet Allocation) topic modeling using Gensim library.\n\nApproach:\n- Created id2word dictionary from tokenized tweets\n- Filtered extremes: no_below=100, no_above=0.7\n- Built corpus using doc2bow\n- Applied LdaMulticore with 3 topics, 5 passes, random_state=42\n- Extracted top words from each topic\n- Obtained topic probabilities for each tweet\n\nTools: Python, Gensim, scikit-learn, pandas, spaCy\n\nRole: Computational social science research focused on Twitter analysis and topic modeling.
