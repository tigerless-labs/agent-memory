---
name: 6-step-nlp-pipeline-for-organizing-90-000-100-000-crime-terrorism-politics-docum
abstract: "6-step NLP pipeline for organizing 90,000-100,000 crime/terrorism/politics documents"
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-20
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Project Scope
- **Document volume**: 90,000-100,000 documents
- **Document format**: 1-5 pages each, with very little structured data
- **Subject matter**: international crime, terrorism, politics

## Recommended Organizational Approach

Recommended 6-step NLP pipeline:

1. **Text Cleaning** — Remove irrelevant characters, punctuation, stop words; normalize (lowercase)
2. **Document Parsing** — Extract constituent parts: title, author, date, body text
3. **Entity Extraction** — Identify key entities (names, organizations, locations) using NER, POS tagging, dependency parsing
4. **Topic Modeling** — Identify main topics and themes; organize by common patterns
5. **Sentiment Analysis** — Understand tone and emotions; track sentiment shifts
6. **Document Classification** — Classify by content category (crime, terrorism, politics) for filtering

This approach enables quick search, filtering, and pattern identification across the corpus.
