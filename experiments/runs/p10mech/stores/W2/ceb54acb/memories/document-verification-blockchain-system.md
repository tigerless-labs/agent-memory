---
created: 2026-09-02T20:56:55.309452611Z
updated: 2026-09-02T20:56:55.309452611Z
weight: 1.0
last_accessed: 2026-09-02T20:56:55.309452611Z
access_count: 0
pinned: false
links: []
abstract: Document verification system May 2023 - online submission, OCR/NLP/ML authenticity checking, blockchain storage, government agency approval for BIR income tax returns and Office of Permits business permits, automatic blockchain integration after approval
---

## Overview
System for scanning and verifying document authenticity using blockchain and AI. Documents submitted online; system checks blockchain; if not found, sends to authorized government agency for approval and verification; once approved, automatically stores in blockchain.

## Government Agencies Involved
- BIR (Bureau of Internal Revenue) for income tax returns
- Office of Permits and Licenses for business permit documents

## Algorithm Flow
1. User submits document(s) online
2. System checks if document exists in blockchain
3. If already stored: apply verifiable credentials algorithm to verify authenticity
4. If not stored: send request to concerned government agency
5. Agency reviews and verifies authenticity
6. Once approved, automatically store in blockchain using AI method
7. Notify user of verification results

## AI Methods Used
- OCR: extract text
- NLP: analyze text, identify key features (date, name, ID number)
- ML: compare extracted features with reference documents
- Verifiable credentials algorithm: create digital signature
- Machine learning: identify patterns and anomalies for fraud detection