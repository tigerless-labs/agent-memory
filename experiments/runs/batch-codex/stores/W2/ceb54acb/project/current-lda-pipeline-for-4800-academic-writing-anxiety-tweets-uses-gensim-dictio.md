---
name: current-lda-pipeline-for-4800-academic-writing-anxiety-tweets-uses-gensim-dictio
abstract: Current LDA pipeline for 4800 academic writing anxiety tweets uses Gensim Dictionary and LdaMulticore with 3 topics
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

Current topic-modeling pipeline: build `Dictionary(clean_tweets_df['tokens'])`; call `filter_extremes(no_below=100, no_above=0.7)`; create corpus with `[id2word.doc2bow(d) for d in clean_tweets_df['tokens']]`; fit `LdaMulticore(corpus=corpus, num_topics=3, id2word=id2word, workers=2, passes=5, random_state=42)`; extract the top 10 printed words per topic; and obtain per-tweet probabilities with `base_model.get_document_topics(corpus)`. Quality should be checked using topic coherence and interpretability, with tokenization, topic count, and hyperparameters adjusted accordingly.
