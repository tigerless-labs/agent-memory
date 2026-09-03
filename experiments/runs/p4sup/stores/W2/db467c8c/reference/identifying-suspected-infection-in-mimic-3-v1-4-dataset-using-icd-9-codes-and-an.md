---
name: identifying-suspected-infection-in-mimic-3-v1-4-dataset-using-icd-9-codes-and-an
abstract: Identifying suspected infection in MIMIC-3 v1.4 dataset using ICD-9 codes and antibiotics
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-06-29
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Sepsis-3 definition requires suspected infection. Two methods in MIMIC-3 v1.4 dataset: 1) ICD-9 diagnosis codes (001-018, 020-041, 090, 112, 114-115, 380, 481-488, 518, 995-996 ranges) from DIAGNOSES_ICD table. 2) Antibiotic administration from PRESCRIPTIONS table: amoxicillin, cephalexin, ciprofloxacin, clindamycin, doxycycline, ertapenem, gentamicin, imipenem, levofloxacin, meropenem, moxifloxacin. Use LIKE pattern matching to identify patients meeting infection criteria within relevant time window relative to organ dysfunction.
