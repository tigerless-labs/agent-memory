# 域:Write(W)

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**
2. **Context and Scope** — 从宿主会话到真源落盘的全链路;写入策略本身是实验变量(ADR-006)。
3. **Goals / Non-Goals** — 目标:写入率由机制保证、零任务阻塞、原意最大保留、系统层零丢。
   不做:库内 LLM 蒸馏(ADR-002)、写入时做管理(推迟到 M)。

## 4. The Actual Design

**正确性基础:蒸馏水位线。**每个 transcript 记录「蒸馏到哪了」;一切触发点的语义
= 推进水位线,输入永远是增量。水位线只在蒸馏落盘后推进(交接不算完成),
因此隔断重开 → 幂等;钩子失灵 → 其他触发点照推;崩溃 → 尾巴留在水位线之后,
下次触发原样补收。触发器从「必须可靠」降为「越多越好」。

**触发点**(挂通用时刻,方言见 api/hooks.md):停顿点 + 淘汰点(钩子,主力)、
agent 自主(skill 教,辅助)、cron(兜底)。

**W 选项矩阵(实验变量,P2 裁决,见 experiment-harness)**:

| 选项 | 机制 | 宿主要求 |
|---|---|---|
| W0 | 无记忆(空白对照) | — |
| W1 | 边界主 agent 自写(阻塞收尾数秒,cache 命中) | 有钩子 |
| W2 | 边界会话 fork 异步(零阻塞,cache 价,一手 context) | 有钩子+fork |
| W3 | cron 借宿主 CLI 冷读 trace 蒸馏(零 harness 依赖,全价) | 能起进程 |
| W4 | inline 实时写(抢带宽 baseline) | skill 即可 |

**写入管线(库侧,零 LLM,确定性)**:frontmatter 校验(非法拒收)→ content-hash
增量重索引(embedding 插件开启时对 abstract+正文;超长按 heading 多条,命中返回整文件)
→ links 解析校验 → MEMORY.md 索引行 → provenance 摘录 append 进 archive。

**写前纪律(skill 教)**:先 recall 查重——同原子存在时判「旧内容还会被问到吗」:
会 → supersede;不会 → 原地 update;不同原子 → 新建。相对日期转绝对;归对类型域。
写入只建断言边,不建相似边。

5. **Alternatives Considered** — 库内异步 LLM Writer(实习生方案):统一策略优点真实,
   但违反 ADR-002 四红线;其 proposal/validator/事务纪律被吸收进 M 的 T1 与索引层 revision。
6. **Cross-cutting** — 蒸馏漏 ≠ 系统丢:原料层兜底(Invariant 4);敏感信息边界写
   天然留 review 窗口。
7. **Risks** — 边界 hindsight 优于实时蒸馏无对照证据(P2 实验裁决);
   cache TTL 约束 fork 必须边界立即执行。
