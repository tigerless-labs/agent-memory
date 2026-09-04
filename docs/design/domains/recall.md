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

**检索管线(库侧,零 LLM)**:资格过滤先于相关性(scope 路径前缀、两态、`--as-of` 时间点、
`--deep` 才进原料)→ BM25(核心;FTS5 索引 abstract+正文)‖ 向量(插件,开启时 RRF 融合)
→ 排序 `score = 相关度 × weight × 时效因子` → 返回 L0 列表 → 写 access log 喂 M。
默认面只查现役索引(active);`--as-of` 查历史索引(invalid,按 valid_from / invalid_at 区间判有效);
两张索引永远不混排。

**原料检索面**:`archive/sessions/` 的 trace 单独建 FTS,锚点是消息序号,只应答 `--deep`。原料命中作为
**证据列表单独返回**,不与记忆混排,每条带会话时间与「已被哪些记忆引用」——它是证据不是知识;
反复命中却无人引用的片段是 M 提「补蒸馏」的依据。这是 Invariant 4 的检索一半:
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
