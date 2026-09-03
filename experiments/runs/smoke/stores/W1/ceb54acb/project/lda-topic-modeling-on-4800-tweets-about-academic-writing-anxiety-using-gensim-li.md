---
name: lda-topic-modeling-on-4800-tweets-about-academic-writing-anxiety-using-gensim-li
abstract: LDA topic modeling on 4800 tweets about academic writing anxiety using Gensim library
type: fact
status: active
created: 2026-09-01
updated: 2026-09-01
valid_from: 2026-09-01
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Working on computational social science research analyzing Twitter data related to academic writing anxiety.

**Dataset**: 4800 tweets containing the keyword 'academic writing anxiety'

**Methodology**: LDA-based topic modeling using Gensim library
- Number of topics: 3
- Number of passes: 5
- Dictionary filtering: no_below=100 (remove words appearing in <100 tweets), no_above=0.7 (remove words appearing in >70% of tweets)
- Using LdaMulticore with 2 workers
- Random state: 42 for reproducibility

**Output**: Extracting top words per topic, creating human-readable topic labels, obtaining topic probability distributions for each tweet. Using regex to parse topic words from model output.
