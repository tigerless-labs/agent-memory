# PRD:agent-memory v0.1

1. **Metadata** — 作者:Claude(基于调研 40+ 来源);评审:Ryan;2026-09-01;状态 **accepted**

2. **Context and Scope** — 现有记忆系统的共同缺口:R 强、W 靠自觉、独立 M 几乎不存在
(严格口径下 25 个调研对象中仅 3 个)。v0.1 是一个多 agent 共用的本地记忆运行时,
供 Claude Code / Codex CLI / Hermes 等接入同一存储盘。

3. **Goals / Non-Goals**

   目标(三特点):
   - **不漏信息**:AI-native 文件索引 + 检索召回,三轨互备(注入/检索/地址),渐进披露
   - **不丢信息**:M 更新与过期不销毁——supersede 标记 + 三级 archive,失效可回溯(`--as-of`)
   - **低成本高保真写入**:边界触发、fork/自写不阻塞任务、原意最大保留;
     蒸馏面允许漏,系统层零丢(原料 append-only)

   Non-Goals(v0.1 显式不做):
   - 托管服务 / 多租户 ACL / 团队远程共享
   - 学习型策略(learned writer/router/gate)
   - 深层目录树、目录级摘要聚合、图遍历索引(evidence-gated,见 ADR-004/005)
   - 长文档知识库(reference 域整篇文章的检索面另议)

4. **The Actual Design** — 见 architecture/overview.md 与四个 domain 文档。

5. **Alternatives Considered** — DB 真源 + 库内管线路线(实习生方案/Graphiti 谱系):
   工程严谨性更高,但违反迁移自由与平台寄生战略,见 ADR-001/002。

6. **Cross-cutting Concerns** — 记忆是持久注入面(memory poisoning):破坏性操作分级
   (Invariant 6);召回内容一律当数据不当指令;敏感内容不入 MEMORY.md 常驻注入。

7. **Risks / Open Questions** — 质量目标与验收指标:
   - **简单性**:安装 ≤2 步;外部依赖 = 0(除单个可执行物);核心一人一天可读完
   - **通用性**:三宿主(A/B/C 三档能力)同库跑通;A 写 B 读互通;同请求异入口同结果
   - **健壮性**:`rm -rf .index/` 重建零知识损失;中途 kill 后水位线补收;并发写不损坏
   - **效果**:三套主流 benchmark(LongMemEval-V2 / MemoryAgentBench / MemGym),
     R 固定下对比 W 选项,W0 空白对照给出记忆净贡献底线
   - 开放:跨 agent weight 语义;MEMORY.md 注入预算是否按 agent 分;
     「平台内置记忆 = 文件派」样本量 = 1 的外推风险
