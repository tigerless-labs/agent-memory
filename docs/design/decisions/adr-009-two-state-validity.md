# ADR-009: 记忆只有 active 与 invalid 两态,失效只来自替换与删除

**Status**: accepted (2026-09-03)

**Context**: 原设计 active / stale / retired 三级阶梯,中间一级从未接上任何行为;retire 搬文件进
`archive/retired/`,原地 update 覆盖旧正文,旧值去向因操作而异。Graphiti 的做法是一条边只有一个有效区间,
新事实不删旧事实,只给旧边打失效时刻。

**Decision**: status 只有 active 与 invalid,配 valid_from 与 invalid_at 两个时刻。失效只有两个来源:
被后继替换(superseded_by 指向后继,后继 valid_from = 前驱 invalid_at)、被删除(标记,文件不动)。
搬家、改 abstract、追加 links 或 provenance、结算 weight 都不改状态。事实变了必须走替换,原地 update
只允许改非事实字段。invalid 文件原地保留,进历史检索面,只应答 `--as-of`。物理清理是人发起的独立命令。

**Consequences**: 好——「旧记忆去哪」永远只有一个答案;时间轴无缝;M 的每个操作都可逆;
价值化遗忘收成 weight 一个旋钮。坏——文件数只增不减,靠 weight 与人工清理消化;
合并不再追溯事实最早成立的日期,那个信息留在 provenance 里。
