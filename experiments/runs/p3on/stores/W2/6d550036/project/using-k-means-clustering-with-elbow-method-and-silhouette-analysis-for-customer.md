---
name: using-k-means-clustering-with-elbow-method-and-silhouette-analysis-for-customer
abstract: Using k-means clustering with elbow method and silhouette analysis for customer data analysis
type: decision
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

Project analyzing customer data to identify trends and patterns. Decided to use k-means clustering (over hierarchical clustering) with two methods to determine optimal number of clusters:

- **Elbow Method**: Plot within-cluster sum of squares (WCSS) against k values; optimal k is where curve flattens
- **Silhouette Analysis**: Calculate silhouette scores to measure cluster cohesion and separation

**Data preparation approach:**
- Handle missing values (imputation or removal)
- Normalize/scale features (standardization or min-max scaling) since customer data has varying units/scales
- Feature selection to remove low-variance or highly correlated features
- Handle categorical features via one-hot or label encoding
- Identify and handle outliers

**Visualization approach:**
- Scatter plots and pairwise scatter plots for feature relationships
- Heatmaps for correlation matrix
- Dimensionality reduction (PCA or t-SNE) to visualize high-dimensional data in 2D
- Use color schemes to encode meaning (sequential for continuous, categorical for groups)
- Consider accessibility (color blindness)
