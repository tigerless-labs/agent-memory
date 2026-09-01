# ADR-003: BM25 是核心检索,向量是可选插件

**Status**: accepted (2026-09-01)

**Context**: embedding 模型是全设计最重的依赖(本地 ONNX 也 40MB+ 且多平台适配)。
短事实库 + agent 手写 abstract + BM25 全文,字面匹配地板可能够用
(coding 场景高频查询是错误码/命令/专名,BM25 主场)。

**Decision**: 核心 = SQLite FTS5(BM25,索引 abstract+正文),零模型依赖;
向量为可选插件,开启时与 BM25 走 RRF 融合。这是**可测赌注**:P2 跑有/无插件对照,
paraphrase 类查询漏得多则插件转正为默认。

**Consequences**: 好——核心安装零模型、通用性最大化;检索面语义盲区有三轨兜底
(注入轨、地址轨)。坏——paraphrase 召回在核心配置下有已知盲区,依赖实验裁决,
可能返工默认配置。
