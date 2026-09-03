---
name: supermarketdata-csv-dataset-for-retail-sales-analysis
abstract: Supermarketdata CSV dataset for retail sales analysis
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

Dataset used in RStudio with columns: Store, Dept, year, Weekly_Sales

Common R code patterns:
- Filter by year: filter(data, year == 2012)
- Group by store and summarize: group_by(Store) %>% summarize(mean = mean(Weekly_Sales))
- Top departments by sales: group_by(Dept) %>% summarize(total = sum(Weekly_Sales)) %>% arrange(desc(total))
- Boxplot: boxplot(Weekly_Sales ~ Store, data)

Store 10 used as focus for comparison analysis vs other stores.
