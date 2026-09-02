# 域:Manage(M)

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**
2. **Context and Scope** — 写后独立管理:consolidation、价值化遗忘、树演化。本系统的差异化主战场。
3. **Goals / Non-Goals** — 目标:所有「攒够证据才能做对」的决策推迟到睡眠期批处理;
   破坏性操作可审计可回滚。不做:全库周期性 LLM 重写;写入时管理。

## 4. The Actual Design

**触发与输入**:条件自动(距上次 ≥24h 且新增 ≥N session,N 在 config)/ 手动 `sleep` /
空闲;headless 一次性进程(cron → CLI,不需常驻)。输入:记忆文件全量 + access log
使用统计 + archive 原文(裁决矛盾时回溯证据——与只按新旧裁决的 Auto Dream 的关键差异)。

**操作按 authority 分级**(Invariant 6):

| 级 | 权限 | 操作 |
|---|---|---|
| T0 无人值守 | 只增改不删 | 日期规范化;MEMORY.md 预算修剪(降级不删);完全重复合并;staleness 标记;按共现/引用证据补 links;abstract 质量巡检重写(对着同文件正文,有据可依) |
| T1 提案待确认 | 出提案不执行 | 相似条目合并;supersede 标记;weight 大幅调降;**树结构演化**——聚簇成目(域根平铺按 links 密度/前缀/共现识别,同话题 ≥阈值提案建目搬家;slug-id 保证 mv 不断链)、冷话题降档、命名分裂合并 |
| T2 人在环 | 仅人发起 | 物理删除;跨目录大规模重组 |

**价值化遗忘**:weight ← 使用统计(召回且被引用 → 升;长期未召回 → 缓降)+
显式 boost/penalize。淘汰 = 三级缓冲逐级降(退出 MEMORY.md → 退出默认检索面 → 归档),
每级可逆。weight 是低频结算值,由 M 批量写回 frontmatter(读永不改真源,Invariant 3)。

**审计与确认**:每次睡眠产出 dream-report(动了什么、为什么、证据指针),git 一睡眠一 commit。
提案带稳定标识,确认与否决记入提案账本——与记忆文件同为真源,不可由索引重建;已决定的提案不再
重复提出,未决定的每次睡眠重新呈现。确认经 CLI 与 MCP 同一入口(Invariant 8),应用走同一条写入
管线(Invariant 2)。确认只把 T1 提案变成已批准的 T1 操作,不把 T2 操作降级——目录重组仍需人发起。

5. **Alternatives Considered** — change-scoped 写时维护(实习生/TEPA 路线):
   已部分吸收(写时 supersede 在 W 纪律里);纯写时无法做价值化遗忘与跨条目整理。
6. **Cross-cutting** — M 是 memory poisoning 的主防线:无人链路 append-only 语义 +
   全量审计,回应 second-brain(人在环)与 Auto Dream(无人删)两派之争的取中。
7. **Risks** — M 干预净价值未测,且**现有回放协议测不出**:单轮写入-单轮考试的套件不产生
   陈旧、不产生被取代的值、不产生足够密的话题,T0 能触发的只有补边与 weight 结算,对得分中性
   (evidence: experiments/results/p2-optimisation.md#p7)。需要纵向协议(session/recall/sleep
   交替推进模拟时间)才谈得上度量。**可证伪声明**(源 artifact):若 staleness 净值曲线为负或
   趋零,本层应被砍掉——该判据至今无法执行,这比它失败更值得优先解决。
   错合并率需在 dream-report 上人工抽查积累数据。
