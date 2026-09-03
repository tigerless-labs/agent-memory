# 设计树索引

来源:两份已评审 artifact(2026-09-01,Ryan 审定)——
[五层参考架构](https://claude.ai/code/artifact/338e19f7-5733-4b8a-8409-ba58eecc92f3)与
[实验系统设计](https://claude.ai/code/artifact/d4c0d335-2a0a-47f0-b8e4-e182b998ad36)。
两者是本树的上游,改设计前先回读;覆盖核对见
[artifact-conformance.md](artifact-conformance.md)。
全部文档状态 `accepted`,除标注 `proposed` 者。

## requirements/
- [prd.md](requirements/prd.md) — 产品定义、三特点、质量目标与验收指标

## architecture/
- [overview.md](architecture/overview.md) — 系统总览:三个物理组件、一条写路径、三条读轨、实验系统位置
- [rules.md](architecture/rules.md) — 全局规则:真源纪律、写路径、并发、配置

## api/
- [cli.md](api/cli.md) — CLI 面(universal fallback + admin)
- [mcp.md](api/mcp.md) — MCP 工具面(少而高层)
- [hooks.md](api/hooks.md) — 钩子接入契约(停顿点/淘汰点,按宿主方言)

## domains/
- [storage.md](domains/storage.md) — DS:真源树、文件边界公理、frontmatter、三级 archive、索引投影
- [write.md](domains/write.md) — W:水位线、触发阶梯、写入管线、W 选项(实验变量)
- [manage.md](domains/manage.md) — M:睡眠期 consolidation、authority 分级、价值化遗忘、树演化
- [recall.md](domains/recall.md) — R:三轨、检索管线、渐进披露、评分
- [experiment-harness.md](domains/experiment-harness.md) — 实验系统:记忆系统 × 宿主 × W 对比,覆盖率探针

## decisions/
- [adr-001-file-truth.md](decisions/adr-001-file-truth.md) — 文件真源,不用 DB 真源
- [adr-002-no-llm-in-core.md](decisions/adr-002-no-llm-in-core.md) — 库核心零 LLM,智能借用
- [adr-003-bm25-core-vector-plugin.md](decisions/adr-003-bm25-core-vector-plugin.md) — BM25 核心,向量插件
- [adr-004-graph-as-data.md](decisions/adr-004-graph-as-data.md) — 图是文件里的数据,不是索引
- [adr-005-tree-emerges-from-manage.md](decisions/adr-005-tree-emerges-from-manage.md) — 树由 M 聚簇产生
- [adr-006-write-as-experiment.md](decisions/adr-006-write-as-experiment.md) — 写入选项不拍板,实验裁决
- [adr-007-implementation-language.md](decisions/adr-007-implementation-language.md) — 实现语言(**proposed,待 Ryan 签字**)
