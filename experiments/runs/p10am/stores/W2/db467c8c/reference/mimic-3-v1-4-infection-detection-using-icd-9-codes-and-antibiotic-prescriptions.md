---
name: mimic-3-v1-4-infection-detection-using-icd-9-codes-and-antibiotic-prescriptions
abstract: MIMIC-3 v1.4 infection detection using ICD-9 codes and antibiotic prescriptions for Sepsis-3 analysis
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Suspected infection in MIMIC-3 combines ICD-9 diagnosis codes (001-039, 090, 112-115, 380, 481-488, 518, 995-996) from DIAGNOSES_ICD table with antibiotic prescriptions (amoxicillin, cephalexin, ciprofloxacin, clindamycin, doxycycline, ertapenem, gentamicin, imipenem, levofloxacin, meropenem, moxifloxacin) from PRESCRIPTIONS table. Use with temporal SOFA changes for Sepsis-3 definition.
