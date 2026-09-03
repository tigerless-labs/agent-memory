---
name: kubernetes-daemonset-wildcard-toleration-pattern-for-any-taints
abstract: Kubernetes DaemonSet wildcard toleration pattern for any taints
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

To make a Kubernetes DaemonSet tolerate any taints, add wildcard tolerations to the PodSpec:

```yaml
tolerations:
- operator: Exists
  effect: NoSchedule
- operator: Exists
  effect: PreferNoSchedule
- operator: Exists
  effect: NoExecute
```

The `operator: Exists` allows pods to tolerate any taint regardless of key or value. Must specify all three taint effects (NoSchedule, PreferNoSchedule, NoExecute) to ensure scheduling on nodes with any taint effect.
