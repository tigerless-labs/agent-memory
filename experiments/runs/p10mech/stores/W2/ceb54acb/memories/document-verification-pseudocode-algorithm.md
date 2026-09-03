---
created: 2026-09-02T20:57:00.632742591Z
updated: 2026-09-02T20:57:00.632742591Z
weight: 1.0
last_accessed: 2026-09-02T20:57:00.632742591Z
access_count: 0
pinned: false
links: []
abstract: Pseudocode algorithm for document verification system with online submission, blockchain check, agency request workflow, and AI-based authenticity verification using OCR, NLP, and machine learning
---

## Pseudocode Algorithm

```
1. User submits document(s) for verification online
2. System checks if the document(s) are already stored in the blockchain
3. If the document(s) are already stored in the blockchain
   - Apply verifiable credentials algorithm to verify authenticity
4. Else (if not stored in blockchain)
   - Send request for approval to concerned government agency
   - (e.g., BIR for income tax returns, Office of Permits and Licenses for business permits)
5. Concerned government agency reviews request and verifies authenticity
6. Once agency approves request
   - Execute AI-based method:
     a. Use OCR to extract text from document(s)
     b. Apply NLP to analyze text and identify key features/elements
        (date, name, ID number, etc.)
     c. Use ML algorithms to compare extracted features with reference documents
        to verify authenticity
     d. Apply verifiable credentials algorithm to create digital signature
     e. Automatically store verified document(s) in blockchain
7. System notifies user of verification results
8. Provide user access to verified document(s) in blockchain
```

## Key Features
- Online document submission
- Blockchain lookup before requesting approval
- Government agency approval workflow integration
- Automatic blockchain storage upon approval
- AI-powered authenticity verification through ML comparison with reference documents
- Digital signature creation via verifiable credentials
- User notification of results
- Tamper-proof storage and access