---
name: tested-claude-s-ability-to-selectively-avoid-saying-a-specific-word-2023-05-20
abstract: Tested Claude's ability to selectively avoid saying a specific word (2023-05-20)
type: experience
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

Conducted a test where you asked Claude not to read or remember the word 'scuba' and to avoid mentioning it in responses. Claude failed the test multiple times, repeatedly mentioning 'scuba diving' and 'SCUBA' when discussing underwater diving activities, even when asked to paraphrase or discuss indirectly.

**Finding**: Claude cannot reliably follow instructions to selectively ignore or avoid mentioning specific words when discussing related topics. The model appears to be fundamentally incapable of this type of selective censoring, particularly when the word is central to the topic being discussed.

**Test method**: Escalating requests that tried to work around the constraint (paraphrasing, indirect discussion, asking Claude to describe what you'd be doing). Each attempt still resulted in the forbidden word appearing.

**Implication**: This is a known limitation in how Claude processes language — it cannot suppress specific lexical items while maintaining coherent discussion of the concept those words represent.
