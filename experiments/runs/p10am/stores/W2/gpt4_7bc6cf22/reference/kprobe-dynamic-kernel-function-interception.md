---
name: kprobe-dynamic-kernel-function-interception
abstract: "Kprobe: dynamic kernel function interception"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-03-07
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Kprobe is a Linux kernel mechanism to dynamically intercept specific function calls and execute custom code in response.

**Use cases:**
- Diagnose and debug kernel issues
- Understand what specific kernel functions are doing
- Modify kernel state on-the-fly
- Trace execution patterns
- Debug issues that are difficult to reproduce

Custom code (handler) is executed when the probe is triggered, allowing non-invasive inspection and modification of kernel behavior without recompilation.
