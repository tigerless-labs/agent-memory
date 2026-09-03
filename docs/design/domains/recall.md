# 域:Recall(R)

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**
2. **Context and Scope** — 三条读轨与检索管线;实验期间 R 全程固定(Invariant 9)。
3. **Goals / Non-Goals** — 目标:不漏信息(三轨互备)、context 经济(渐进披露)。
   不做:LLM rerank、learned router、图扩展索引(ADR-004)。

## 4. The Actual Design

**三轨互备**:
- 注入轨:SessionStart 注入 MEMORY.md(预算内)——确定性保底,agent 无感
- 检索轨:`recall <query>` → L0 列表——agent 自觉调用(skill 教「任务前先查」)
- 地址轨:目录树 ls/glob/grep——语义/字面检索失手时的第二条可达路径;
  同目录 = 免费邻域(归属边遍历)

**检索管线(库侧,零 LLM)**:资格过滤先于相关性(scope 路径前缀、status、
`--as-of` 时间点、`--deep` 才进 archive 与原料)→ BM25(核心;FTS5 索引 abstract+正文)
‖ 向量(插件,开启时 RRF 融合)→ 排序 `score = 相关度 × weight × 时效因子`
(active 优先,superseded 默认排除)→ 返回 L0 列表 → 写 access log 喂 M。

**原料检索面**:`archive/sessions/` 的 trace 单独建 FTS,只应答 `--deep`,不带 weight
与时效,且按系数压在蒸馏记忆之下——它是证据不是知识。这是 Invariant 4 的检索一半:
原料存下来而查不到,兜底就只存在于磁盘上。

**披露由谁决定,是可测的**(evidence: experiments/results/p2-optimisation.md#p9——
把这一次性调用交到 agent 手里、自由度全保留,得分与库直接代劳无差异 p=1.00,
两者都显著高于没有该调用的同一 agent p=0.0003;即收益来自读取面本身,不来自限制宿主):`recall` 返回 L0 列表把梯子交给调用方——知道自己要找什么的
agent 用得好;不知道的 agent 自驱检索会把同一个库的得分在重放之间晃动 ±7/120,且显著低于
同库按固定策略读(evidence: experiments/results/p2-optimisation.md)。故梯子也提供一次性形态:
库自己跑 recall、打开头部条目到全文、交回可直接推理的上下文。检索、打分、资格过滤全不变,
变的只是「谁决定何时停」。弱宿主(不擅长驱动工具的 C 档)因此也能吃到完整读取面。

**渐进披露(每级贵一个量级,每级可停)**:索引行 → abstract → 全文 → `--deep` 原料;
长文件加两个免费中间级:命中锚点(`路径#小节`,切分信息透传)与机械大纲
(读时按标题现算)。命中返回单位永远是完整文件(切分只为索引)。

5. **Alternatives Considered** — OpenViking 父子分数传播 + L0 语义面
   (长文档场景备选,进 TODO);MemCLI 只 embed abstract(检索质量押一句话,否)。
6. **Cross-cutting** — 召回内容注入 prompt 时一律作为数据呈现;
   recall 结果携带路径与时间戳,可解释可溯源。
7. **Risks** — 「BM25 够用」是可测赌注:benchmark 有/无向量插件对照,
   paraphrase 类查询漏得多则插件转正(P2 顺带产出)。

## 8. Progressive raw-trace Read experiment (proposed)

### Problem and hypothesis

Current evidence points first to Write coverage: when the answer reached a memory file, normal
recall often finds it. This experiment therefore does not change retrieval. It tests the narrower
hypothesis that distillation can preserve the durable state while dropping a date, number, path,
error, quotation, or decision history that still exists in the archived trace.

The authority rule is:

> Memory says what is currently believed; raw trace is evidence of what happened then.

An active memory may support a current fact. A superseded or retired memory may support a
historical answer only. Raw trace may recover detail or history, but must not override an eligible
current memory. If neither surface directly supports the answer, the host abstains rather than
completing it from a related passage. `stale` remains eligible today and its status is carried on
the recall hit; this experiment does not silently promote it or change that existing policy.

### Current implementation facts

- `Recall.recall` queries SQLite FTS5 over abstract/body chunks, qualifies records by scope,
  archived/retired state, supersede chain, and optional `as_of`, then applies relevance × weight ×
  recency. `Hit` contains name, absolute path, abstract/snippet, anchor, heading, domain, type,
  updated, status, weight, relevance, recency, score, and source.
- `--deep` currently widens the limit, admits archived/retired memories, and—when `raw_enabled`—
  globally searches a separate FTS5 `raw_chunks` table. Raw chunks are non-overlapping groups of
  nonblank transcript lines, identified by session-derived name/path and a numeric chunk anchor.
  They are appended to memory hits, down-weighted by `raw_relevance_factor`, sorted, and truncated.
  This is global raw RAG, not a provenance-guided fallback.
- `Store.read` still exposes `abstract`, mechanically computed `outline`, and `full`. `mem recall`
  returns the list, `mem read` opens one memory, and `mem context` calls the separate
  `core.context` builder. The builder opens the first `context_full_text_entries` hits fully and
  renders the rest as abstracts. With deep recall, a raw hit happens to be opened through
  `Store.read`; that fails and is swallowed, so only the raw snippet carried in the hit is shown.
- Session traces are append-only `.txt` files under `archive/sessions/`; retirement moves memory
  Markdown under `archive/retired/`. Superseding leaves the predecessor on disk and excludes it
  from current recall; `as_of` can select it before its successor becomes valid, while `deep` does
  not override the supersede filter. Manage marks idle active records stale and retirement is
  explicit T2. Raw sessions have no status/supersede coupling and are not deleted by these
  operations. They therefore remain evidence, never an alternate active set.
- A memory's `provenance` field deterministically names excerpt files under
  `archive/provenance/<memory>/`. Those files contain recorded time, writer agent as `source`, and
  excerpt text. They do **not** contain session ID, raw path, chunk anchor, or offsets. Thus a memory
  can reach its stored excerpt exactly, but cannot deterministically reach the containing raw
  session/span. A verbatim excerpt can be matched back against existing sessions at read/index
  time when unique; zero or multiple matches must remain unresolved.

### Minimal Read flow

```text
query -> normal eligible memory recall -> selected memory abstract/outline/full
      -> only if a requested detail is still absent
      -> that memory's provenance excerpt
      -> uniquely derived containing raw chunk plus at most one adjacent chunk, if needed
      -> answer under the authority rule, or abstain
```

R0 is today's normal memory-only Context path (`deep=false`). R1 changes the disclosure path, not
BM25 memory candidate generation or ranking: it runs that same normal recall first, then treats an
explicit `deep` request/arm as permission for linked fallback rather than mixing a global raw
search into the first result list. Teach the shared Context/read contract to perform that fallback.
Agentic hosts may also continue down this ladder when the opened memory lacks the requested
specific. A small deterministic lexical hint (dates, numbers, paths, error text, or requested
wording) may later bound eligible cases, but is not required for the first paired test. There is no
runtime LLM sufficiency judge, router, or new query classifier.

The first implementation should expose provenance through the existing Read/Context surface and
use the provenance path already stored on `MemoryRecord`. Prefer exact excerpt-to-session matching
against existing raw files/index metadata. If benchmark stores prove that mapping ambiguous, the
smallest unavoidable addition is a source-session locator written beside the provenance excerpt;
do not introduce a provenance graph. Because old stores lack it, fallback must degrade to the
excerpt and remain backward compatible.

### Non-goals and expected touchpoints

No Write redesign; no new Recall subsystem or Retriever rewrite; no vector/index implementation;
no graph retrieval; no runtime LLM router/judge; no filesystem/Markdown truth change; and no schema
or config expansion unless real stores prove session derivation unavoidable. Existing stale,
supersede, retirement, and raw append-only behavior stays authoritative.

Likely implementation touchpoints are `core/context.py` (the host-neutral policy), `core/store.py`
or a small archive reader (linked evidence), `core/raw_index.py` only if exact/nearby lookup can
reuse it, CLI/MCP response rendering, and their existing recall/context/entry-equivalence tests.
`core/recall.py` may need to keep global raw hits out of the progressive path, but should not gain
another retrieval pipeline.
