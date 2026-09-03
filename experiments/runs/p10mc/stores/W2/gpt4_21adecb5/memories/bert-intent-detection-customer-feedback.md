---
created: 2026-09-03T01:38:10.063213896Z
updated: 2026-09-03T01:38:10.063213896Z
weight: 1.0
last_accessed: 2026-09-03T01:38:10.063213896Z
access_count: 0
pinned: false
links: []
abstract: BERT for intent detection in customer feedback; datasets CLINC150 (15K samples), HWU64 (64K samples), Amazon Product Reviews, Yelp; intent examples request refund, report issue, provide feedback; intent embeddings, intent masks, hierarchical intent
---

## BERT Adaptation for Intent Detection

**Dataset Options:**
1. **CLINC150** — 15,000 customer feedback samples with annotated intents
2. **HWU64** — 64,000 customer feedback samples with annotated intents
3. **Amazon Product Reviews** — with intent annotations
4. **Yelp Dataset** — with intent annotations

**Intent Examples (Clothing Brand Context):**
- "return_policy" — questions about returns
- "size_issue" — complaints about sizing
- "style_suggestion" — feature requests
- "report_issue" — technical or quality problems
- "request_refund" — explicit refund requests

**Adaptation Process:**

1. **Intent Identification** — Identify customer goals/intents in feedback

2. **Intent-Specific Tokenization** — Add intent tokens representing identified intents

3. **Intent-Based Input Format:**
   - Input IDs (with intent-specific tokens)
   - Attention Masks
   - Intent Masks (1 for intent-relevant tokens, 0 otherwise)
   - Intent Labels (specific intent categories)

4. **Model Architecture Components:**
   - Intent-based attention layers (focus on intent signals)
   - Intent-aware pooling layers (weight intent tokens appropriately)

5. **Training Tasks:**
   - Intent identification
   - Intent classification

**Advanced Techniques:**
- Intent embeddings (semantic representation of each intent)
- Intent-aware weighting (attention focusing on intent signals)
- Hierarchical intent detection (primary intent → sub-intent → category)
- Multitask learning (joint intent detection with sentiment/aspect analysis)
- Attention visualization for explaining predictions

**Use Case:** Automatically route customer feedback to appropriate departments or identify action items