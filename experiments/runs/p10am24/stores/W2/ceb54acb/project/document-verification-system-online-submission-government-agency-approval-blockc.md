---
name: document-verification-system-online-submission-government-agency-approval-blockc
abstract: "Document verification system: online submission, government agency approval, blockchain storage with OCR/NLP/ML pipeline (May 2023 design)"
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-23
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Project: Digital Document Verification System

**Status:** Designed and planned (May 23, 2023)

**Key Requirements:**
1. **Online Submission:** Users can submit documents for verification online
2. **Government Agency Approval Workflow:** If documents not yet in blockchain, system sends request to authorized agencies (BIR for tax returns, Office of Permits & Licenses for business permits)
3. **Automatic Blockchain Storage:** Once approved by agency, verified documents automatically stored on blockchain
4. **AI-Based Verification:** Novel machine learning approach integrated into verification pipeline

**Technical Algorithm & Workflow:**

1. User submits document(s) online
2. System checks if document(s) already in blockchain
3. If in blockchain → apply verifiable credentials algorithm to verify authenticity
4. If not in blockchain → send approval request to concerned government agency
5. Agency reviews and verifies document authenticity
6. Upon agency approval, system automatically stores using AI pipeline:
   - **OCR (Optical Character Recognition):** Extract text from documents
   - **NLP (Natural Language Processing):** Analyze text, identify key features (date, name, ID number, etc.)
   - **Machine Learning:** Compare extracted features with reference documents to verify authenticity
   - **Verifiable Credentials Algorithm:** Create digital signature and store in blockchain
7. System notifies user of verification results and provides blockchain access

**Technology Stack:**
- OCR engine
- NLP/Text analysis
- Machine Learning algorithms
- Blockchain with verifiable credentials
- Digital signatures & encryption
- Anomaly detection for fraud identification

**Benefits:**
- Tamper-proof storage
- Enhanced security & accuracy
- Reduced fraud risk
- Streamlined verification process
