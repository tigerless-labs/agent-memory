# ADR-001: markdown 文件是唯一真源,SQLite 只做投影

**Status**: accepted (2026-09-01)

**Context**: 两条谱系二选一——DB 真源+库内管线(Graphiti/实习生方案:事务、revision、
并发严谨)vs 文件真源+索引缓存(auto-memory/MemCLI:可读、可 git、可迁移)。
DB 真源连带一套投影同步子系统(vault 单向生成、回写禁止)。

**Decision**: markdown 文件为唯一真源;SQLite 承载 FTS/向量/access log/revision 审计,
可整删重建。事务纪律(revision 链、change_set)吸收进索引层,不改变真源地位。

**Consequences**: 好——迁移自由(数据比工具活得久)、平台寄生(与 Claude Code
auto-memory 目录兼容)、用户可直接编辑自己的记忆、无投影同步子系统。
坏——并发靠 flock+last-write-wins+git 兜底,弱于 DB 事务;access log 不可重建
(接受:遥测非知识)。
