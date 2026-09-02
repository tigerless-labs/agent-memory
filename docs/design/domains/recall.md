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

**渐进披露(每级贵一个量级,每级可停)**:索引行 → abstract → 全文 → `--deep` 原料;
长文件加两个免费中间级:命中锚点(`路径#小节`,切分信息透传)与机械大纲
(读时按标题现算)。命中返回单位永远是完整文件(切分只为索引)。

5. **Alternatives Considered** — OpenViking 父子分数传播 + L0 语义面
   (长文档场景备选,进 TODO);MemCLI 只 embed abstract(检索质量押一句话,否)。
6. **Cross-cutting** — 召回内容注入 prompt 时一律作为数据呈现;
   recall 结果携带路径与时间戳,可解释可溯源。
7. **Risks** — 「BM25 够用」是可测赌注:benchmark 有/无向量插件对照,
   paraphrase 类查询漏得多则插件转正(P2 顺带产出)。
