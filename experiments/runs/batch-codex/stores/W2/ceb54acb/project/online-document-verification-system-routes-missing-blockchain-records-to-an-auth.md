---
name: online-document-verification-system-routes-missing-blockchain-records-to-an-auth
abstract: Online document-verification system routes missing blockchain records to an authorized government agency and stores approved records automatically
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

Required workflow for the document-verification system: accept documents submitted online; check whether each document is already stored on the blockchain; verify existing records with verifiable credentials; if absent, send an approval request to the authorized agency, such as the BIR for an income tax return or the office of permits and licenses for a business permit document; after agency approval and verification, automatically store the verified document on the blockchain and notify the user. The proposed AI flow uses OCR to extract text, NLP to identify fields such as date, name, and ID number, machine learning to compare extracted features against reference documents and detect anomalies, and a verifiable-credentials digital signature before blockchain storage.
