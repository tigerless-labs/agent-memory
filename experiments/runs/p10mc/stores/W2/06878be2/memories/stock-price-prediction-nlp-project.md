---
created: 2026-09-02T23:49:59.249485457Z
updated: 2026-09-02T23:49:59.249485457Z
weight: 1.0
last_accessed: 2026-09-02T23:49:59.249485457Z
access_count: 0
pinned: false
links: []
abstract: Stock price prediction project using NLP - May 2023; combines historical data and news articles; News API and Quandl for data collection; sentiment analysis with rule-based, Naive Bayes, SVMs, CNNs, and RNNs
---

## Project Overview
Predictive model to forecast stock prices combining:
- Historical stock price data
- Sentiment and tone analysis of news articles
- NLP feature extraction

## Data Collection Plan
- News data source: News API
- Stock data source: Quandl
- Time period: Historical data with corresponding news articles

## Data Preprocessing
- Libraries: NLTK and spaCy
- Tasks: Clean text, tokenization, remove stop words, stemming/lemmatization
- Text representation: TF-IDF or word embeddings

## Sentiment Analysis Approaches
- Rule-based methods combined with ML
- Traditional ML models: Naive Bayes, Support Vector Machines (SVMs)
- Deep learning models: CNNs and RNNs for sentiment and tone analysis
- Transfer learning option: Consider BERT or RoBERTa as starting point

## Feature Engineering
Planned features:
- Sentiment scores from news articles
- Named Entity Recognition (NER) to extract entities (companies, locations, people)
- Part-of-speech (POS) tagging
- Topic modeling
- Entity-specific features

## Evaluation Strategy
- Stock prediction metrics: MAE, MSE, RMSPE
- Sentiment model metrics: F1 score, precision, recall
- Plan to experiment with feature combinations and weights