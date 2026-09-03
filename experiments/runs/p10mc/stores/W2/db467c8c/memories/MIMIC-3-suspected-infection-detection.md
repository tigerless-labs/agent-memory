---
created: 2026-09-02T23:28:17.193011581Z
updated: 2026-09-02T23:28:17.193011581Z
weight: 1.0
last_accessed: 2026-09-02T23:28:17.193011581Z
access_count: 0
pinned: false
links: []
abstract: Determining suspected infection in MIMIC-3 v1.4 dataset using Sepsis-3 definition. Two methods - ICD-9 diagnosis codes (001-018, 020-027, 030-041, 090, 112, 114-115, 380, 481-488, 518, 995-996) from DIAGNOSES_ICD table, and antibiotic prescriptions (amoxicillin, cephalexin, ciprofloxacin, clindamycin, doxycycline, ertapenem, gentamicin, imipenem, levofloxacin, meropenem, moxifloxacin) from PRESCRIPTIONS table.
---

## Suspected Infection Detection in MIMIC-3 v1.4

### Method 1: ICD-9 Diagnosis Codes

Query DIAGNOSES_ICD table for infection-related codes in these ranges:
- 001-009: Cholera through non-bacterial enteritis
- 010-018: Tuberculosis
- 020-027: Plague through relapsing fever
- 030-039: Leprosy through whooping cough
- 040-041: Scarlet fever and streptococcal infection
- 090: Syphilis
- 112: Candidiasis
- 114-115: Coccidioidomycosis and histoplasmosis
- 380: Otitis media
- 481-488: Pneumonia and influenza
- 518: Other respiratory disease
- 995-996: Sepsis and complications

### Method 2: Antibiotic Prescriptions

Query PRESCRIPTIONS table for common antibiotics:
- Beta-lactams: amoxicillin, cephalexin, ertapenem, imipenem, meropenem
- Fluoroquinolones: ciprofloxacin, levofloxacin, moxifloxacin
- Other: clindamycin, doxycycline, gentamicin

**Suspected infection confirmed when:** Either ICD-9 infection code present OR antibiotic prescribed, per Sepsis-3 definition.

Both methods use SQL LIKE queries on respective tables to identify matching records.