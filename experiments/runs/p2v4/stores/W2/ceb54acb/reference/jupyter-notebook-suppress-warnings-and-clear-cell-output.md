---
name: jupyter-notebook-suppress-warnings-and-clear-cell-output
abstract: "Jupyter notebook: suppress warnings and clear cell output"
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

Removing warnings from output: Use warnings.filterwarnings('ignore', category=WarningCategory) to filter specific warning types. Use %xmode minimal magic command to reduce error traceback verbosity. Wrap code in warnings.catch_warnings() context manager to temporarily suppress warnings in specific blocks. Clearing cell output: In JupyterLab, press Esc then O to clear output of selected cell, or Esc then Ctrl+O to clear all outputs. Alternatively right-click cell and select 'Clear Outputs' from context menu. Clearing output does not affect cell code or variables, only the displayed output.
