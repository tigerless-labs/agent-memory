# ADR-005: 树由 Manage 聚簇产生,写入零结构决策

**Status**: superseded by ADR-008 (2026-09-03);原文保留供追溯

**Context**: agent 自维护的目录层级随规模退化,更整齐不等于答案质量更高
(evidence: Filesystem-Based Memory, arXiv 2607.26637)。写入时单条记忆不足以
判断话题会不会长大;agent 各自建目必然命名分裂。

**Decision**: 固定四类型域随安装铺好;新记忆平铺进域根。话题目录由 M 睡眠期
「聚簇成目」(links 密度/前缀/共现,≥阈值出 T1 提案建目搬家)。深度硬上限 =
域 + 1 层话题;更深 evidence-gated。

**Consequences**: 好——W 零结构摩擦;命名纪律集中;slug=id 使搬家零断链;
结构滞后于内容(schema-on-read)。坏——早期域根平铺,浏览性靠检索与 MEMORY.md
索引补;聚簇阈值是新参数。
