---
name: jupyter-notebook-output-clearing-and-warning-suppression-techniques
abstract: Jupyter notebook output clearing and warning suppression techniques
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-22
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Clearing output in JupyterLab: select cell, press Esc then O; or right-click and select Clear Outputs; or use Edit menu > Clear All Outputs. Does not affect code or variables.

Suppressing warnings: import warnings; warnings.filterwarnings('ignore', category=WarningCategory). Use context manager with warnings.catch_warnings() for specific code blocks to avoid suppressing all warnings.

Best practice: investigate root cause rather than suppress; update dependencies for deprecated functions; use %xmode minimal for reduced traceback output
