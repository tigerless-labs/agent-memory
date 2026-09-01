# ADR-004: 图是文件里的数据,不建边索引

**Status**: accepted (2026-09-01)

**Context**: 图边对会话记忆的检索增益无独立证据(Graphiti 的图是代码域预编译赌注;
实习生同结论「Graph-by-evidence 而非 Graph-by-default」)。千条规模下图索引是
为不存在的规模预优化。

**Decision**: 边只存在真源文件里(links/wikilink 关联边、superseded_by 时序边、
provenance 证据边、路径归属边)。无 graph.json、无遍历机制;1-hop = agent 读命中
文件跟指针,邻域 = 同目录 ls。索引管线只校验 link 目标存在。

**Consequences**: 好——零基建零维护;边在真源里,未来 benchmark 证明 multi-hop miss
后建边索引是纯投影加法,零迁移。坏——多跳关联查询在 v0.1 无一跳到位的能力
(靠 agent 多步读文件补偿)。
