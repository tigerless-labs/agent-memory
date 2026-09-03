---
created: 2026-09-02T21:31:10.843842118Z
updated: 2026-09-02T21:31:10.843842118Z
weight: 1.0
last_accessed: 2026-09-02T21:31:10.843842118Z
access_count: 0
pinned: false
links: []
abstract: 4800 tweets containing "academic writing anxiety"; LDA topic modeling with Gensim using 3 topics, filter_extremes(no_below=100, no_above=0.7), 5 passes, random_state=42
---

## Dataset
- 4,800 tweets, all containing the keyword "academic writing anxiety"
- Data includes metadata and tokenized text (clean_tweets_df['tokens'])

## LDA Implementation (Gensim)

### Dictionary & Corpus
```python
id2word = Dictionary(clean_tweets_df['tokens'])
id2word.filter_extremes(no_below=100, no_above=0.7)
corpus = [id2word.doc2bow(d) for d in clean_tweets_df['tokens']]
```

### Model
- **LdaMulticore**: num_topics=3, workers=2, passes=5, random_state=42
- Extracted top 10 words per topic
- Obtained document-topic probabilities: `base_model.get_document_topics(corpus)`

## Next Steps
- Evaluate topic coherence and interpretability
- Consider adjusting number of topics or hyperparameters based on results