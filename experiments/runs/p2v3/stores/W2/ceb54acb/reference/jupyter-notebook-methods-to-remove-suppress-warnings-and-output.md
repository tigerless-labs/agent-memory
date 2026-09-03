---
name: jupyter-notebook-methods-to-remove-suppress-warnings-and-output
abstract: "Jupyter notebook: methods to remove/suppress warnings and output"
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

Suppressing Warnings in Jupyter

Use Python warnings module with filterwarnings('ignore', category=WarningCategory) or use context manager with warnings.catch_warnings() for specific code blocks.

Removing Cell Output

JupyterLab: Press Esc then O to toggle output display for selected cell. Any Jupyter: Right-click cell and select Clear Outputs. Menu: Edit > Clear All Outputs for all cells. Clearing output doesn't affect code or variables, just display.

Controlling Traceback: Use %xmode minimal to show only error message and first/last stack frames.

Best Practice: Investigate warning source and fix underlying issue rather than suppressing all warnings.
