---
name: kubernetes-daemonset-wildcard-toleration-pattern-to-tolerate-any-taints
abstract: Kubernetes DaemonSet wildcard toleration pattern to tolerate any taints
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

To make a DaemonSet tolerate any taints, use wildcard tolerations with `operator: Exists` for all taint effects:

```yaml
tolerations:
- operator: Exists
  effect: NoSchedule
- operator: Exists
  effect: PreferNoSchedule
- operator: Exists
  effect: NoExecute
```

The `operator: Exists` field makes the pods tolerate any taint key/value pair. Specifying all three taint effects ensures scheduling works regardless of how the taints are configured.
