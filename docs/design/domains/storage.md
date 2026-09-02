# 域:Storage(DS)

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**
2. **Context and Scope** — 真源、投影、原料三个物理组件的结构与边界。
3. **Goals / Non-Goals** — 目标:人类可读可 git、索引即缓存、失效不销毁。
   不做:深层目录、目录级摘要、图索引(ADR-004/005)。

## 4. The Actual Design

```
memory/
├── MEMORY.md            根索引:一行一条,预算硬约束(常驻注入的唯一来源)
├── user/ project/ reference/ experience/    四个类型域;新记忆平铺进域根
│   └── <topic>/         话题目录不预设,由 M 聚簇产生;深度硬上限 = 域+1 层
├── archive/             append-only,默认不进检索面
│   ├── provenance/      蒸馏证据摘录(统一格式)——永久,摘录级零丢
│   ├── retired/         被淘汰/降级条目
│   └── sessions/        完整 trace 副本(开关默认开;防宿主清理策略)
├── dream-reports/       每次睡眠一份:动了什么、提案了什么、证据指针
├── .index/              全部可重建:manifest(content-hash)、FTS5、原料 FTS、access log
└── .state/              不可重建的运行态:蒸馏水位线、写路径锁、钩子日志
```

`.index/` 与 `.state/` 的分界即「可重建」这条线:删 `.index/` 零知识损失;删 `.state/`
只损失「蒸馏到哪了」,代价是重复蒸馏,不是丢知识。

**单条记忆文件**:frontmatter 携带 name(kebab slug=稳定 id)、abstract(一句话)、
type、status(active/stale/retired,M 的三级降档面)、created/updated、valid_from、
superseded_by、links、weight、author(写入方 agent)、provenance;正文自由 markdown。

**文件边界公理:失效原子 = 文件边界**。一个文件装作为整体一起过期的一份知识
(supersede/weight/召回单位都是文件)。同生共死测试:某部分会单独过期 → 拆;
两文件永远同时失效 → 合。粒度随类型:fact/preference 单事实一档、
experience 一坑一档、procedure 一流程一档。

**图 = 文件里的四种指针**(ADR-004):关联边 links/wikilink、时序边 superseded_by、
证据边 provenance、归属边路径本身。无边索引;遍历 = agent 读文件跟指针。

**trace 分层**:完整 trace 不搬运只记指针(宿主 transcript + 水位线);
`sessions/` 是防宿主清理的压缩副本。零丢分两级:摘录级无条件,全量级依赖该开关。

5. **Alternatives Considered** — SQLite 真源 + Vault 投影(ADR-001 否);
   OpenViking L0/L1/L2 管线生成层(重算贵、非确定,违反索引即缓存)。
6. **Cross-cutting** — author 字段支撑多 agent 矛盾裁决;archive 含原文,export 时提示。
7. **Risks** — access log 不可重建(运行遥测,丢了 = M 证据重新积累,非知识损失);
   长文档检索面(TODO)。
