---
created: 2026-09-02T23:27:58.936014709Z
updated: 2026-09-02T23:27:58.936014709Z
weight: 1.0
last_accessed: 2026-09-02T23:27:58.936014709Z
access_count: 0
pinned: false
links: []
abstract: SOFA score example with dummy patient data - respiratory PaO2/FiO2 200 score 2, cardiovascular MAP 65 mmHg score 1, hepatic bilirubin 2.0 score 0, coagulation platelets 150k INR 1.3 score 0, renal creatinine 1.5 urine 800mL score 0, neurologic GCS 12 score 0. Total SOFA 3 indicates moderate organ dysfunction.
---

## SOFA Score Calculation Example

**Patient parameters:**
- Respiratory: PaO2/FiO2 ratio = 200
- Cardiovascular: Mean arterial pressure (MAP) = 65 mmHg, no vasopressors
- Hepatic: Serum bilirubin = 2.0 mg/dL
- Coagulation: Platelet count = 150,000/mm3, INR = 1.3
- Renal: Serum creatinine = 1.5 mg/dL, urine output = 800 mL in 24 hours
- Neurologic: Glasgow Coma Scale (GCS) = 12

**Component calculations:**

1. Respiratory = 2 — PaO2/FiO2 200 in range 100-400; formula: (200-100)/100 × 2 = 2

2. Cardiovascular = 1 — MAP 65 mmHg < 70 indicates dysfunction without vasopressors

3. Hepatic = 0 — Bilirubin 2.0 is normal (severity threshold > 12 mg/dL)

4. Coagulation = 0 — Platelets 150k and INR 1.3 both normal (thresholds: platelets < 50k or INR > 6.5)

5. Renal = 0 — Creatinine 1.5 and urine 800 mL both normal (thresholds: creatinine > 5.0 or urine < 200 mL/24h)

6. Neurologic = 0 — GCS 12 is normal (severity threshold GCS ≤ 6)

**Total SOFA score = 2 + 1 + 0 + 0 + 0 + 0 = 3**

Score of 3 indicates moderate organ dysfunction per Sepsis-3 criteria.