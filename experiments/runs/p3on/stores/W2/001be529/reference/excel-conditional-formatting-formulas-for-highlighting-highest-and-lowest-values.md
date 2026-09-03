---
name: excel-conditional-formatting-formulas-for-highlighting-highest-and-lowest-values
abstract: Excel conditional formatting formulas for highlighting highest and lowest values
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

To highlight the highest value in a range:
`=MAX($A$1:$A$10)=A1`

To highlight the lowest value:
`=MIN($A$1:$A$10)=A1`

**Usage:**
- Replace $A$1:$A$10 with your actual data range
- Replace A1 with the cell being evaluated  
- Apply to the entire range via conditional formatting
- The formula compares each cell to the max/min of the range
