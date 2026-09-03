---
created: 2026-09-02T20:56:37.770781810Z
updated: 2026-09-02T20:56:37.770781810Z
weight: 1.0
last_accessed: 2026-09-02T20:56:37.770781810Z
access_count: 0
pinned: false
links: []
abstract: Jupyter notebook techniques to suppress warnings and clear output from cells
---

## Clearing cell output

In JupyterLab (and newer Jupyter interfaces without Cell menu):
- Select cell, press `Esc` then `O` to toggle output display
- Right-click cell → "Clear Outputs"
- Edit menu → "Clear All Outputs" (clears all cells)

Note: Clearing output does not affect code or variables, only hides displayed results.

## Suppressing warnings in Python

Use warnings module:
```python
import warnings
warnings.filterwarnings('ignore', category=WarningCategory)
```

Or use context manager to suppress in specific code blocks:
```python
with warnings.catch_warnings():
    warnings.filterwarnings('ignore')
    # code that generates warnings
```

Alternative: Use `%xmode minimal` magic command to reduce traceback verbosity.

**Best practice**: Investigate warning root cause and fix if possible rather than suppressing all warnings.