---
created: 2026-09-02T20:56:33.261907759Z
updated: 2026-09-02T20:56:33.261907759Z
weight: 1.0
last_accessed: 2026-09-02T20:56:33.261907759Z
access_count: 0
pinned: false
links: []
abstract: Twitter dataset of 4,800 tweets containing keyword "academic writing anxiety"; used for topic modeling analysis with LDA
---

## Dataset

- **Size**: 4,800 tweets
- **Common keyword**: "academic writing anxiety"
- **Purpose**: Computational social science research on Twitter using topic modeling
- **Location**: Referenced as `clean_tweets_df` in Jupyter notebook analysis

## Analysis approach

Using Gensim-based LDA topic modeling pipeline:
- Create id2word dictionary from tokenized tweets
- Filter extremes: no_below=100, no_above=0.7
- Create corpus using doc2bow
- LdaMulticore model: 3 topics, 5 passes, 2 workers, random_state=42
- Extract top 10 words per topic for interpretation
- Generate document-topic probabilities for each tweet