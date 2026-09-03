---
name: lda-topic-modeling-pipeline-using-gensim-on-twitter-dataset-3-topics-5-passes
abstract: "LDA topic modeling pipeline using Gensim on Twitter dataset (3 topics, 5 passes)"
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

**LDA Topic Modeling Procedure for Twitter Data**

Using Gensim library to extract topics from tokenized tweets:

1. **Dictionary Creation**
   - Create id2word dictionary from tokenized tweets: `Dictionary(clean_tweets_df['tokens'])`

2. **Filtering**
   - Filter extremes: `id2word.filter_extremes(no_below=100, no_above=0.7)`
   - Removes words appearing in fewer than 100 tweets or more than 70% of tweets

3. **Corpus Creation**
   - Convert to bag-of-words: `corpus = [id2word.doc2bow(d) for d in clean_tweets_df['tokens']]`

4. **LDA Model**
   - Model: `LdaMulticore` from Gensim
   - Parameters:
     - num_topics=3
     - passes=5
     - workers=2
     - random_state=42
   - Extract top 10 words per topic using regex on print_topics() output

5. **Results**
   - Get topic distributions per document: `base_model.get_document_topics(corpus)`
   - Print topics and their top words

**Tools:** Gensim, pandas, regex, scikit-learn (CountVectorizer, LatentDirichletAllocation also mentioned as alternatives)

**Notes:** Quality depends on tokenization quality, number of topics chosen, and hyperparameter tuning. Evaluate coherence and interpretability.
