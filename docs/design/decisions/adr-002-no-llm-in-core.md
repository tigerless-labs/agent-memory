# ADR-002: 库核心零 LLM,智能从消费端借用

**Status**: accepted (2026-09-01);amended 2026-09-03 — 智能不再向宿主借,改为库侧执行器

**Context**: 蒸馏需要 LLM。库内置 LLM 客户端(Mem0/OpenViking/实习生 Async Writer)
统一策略但带来:key 配置与计费、库方成本、写入成为不可见副作用、滑向托管服务形状。
「零配置安装」已被负责人降权,但其余三条仍成立。

**Decision**: 核心依赖清单禁止模型/推理客户端(CI 检查)。蒸馏执行器按档借用:
A 档会话 fork / B 档主 agent 边界自写 / C 档 cron 起用户已装的 agent CLI 冷读 trace。
「LLM proposes, code commits」原则吸收:蒸馏产物过库侧校验器才落盘。

**Consequences**: 好——零 key、复用用户订阅与 cache、写入出现在 agent 自己的
transcript 里天然可审计、多宿主统一由「同一份蒸馏 prompt」而非同一个进程保证。
坏——共库多 agent 的写入风格一致性弱于中央 Writer(靠 schema 校验与 skill 纪律兜);
冷路径(C 档)全价。

**Amendment (2026-09-03)**: 核心包仍不含任何模型客户端,这一条不变。改变的是智能的来源:蒸馏与 M 的推理
全部由 executor 包里的库侧执行器完成(缺省 Gemini 3.7 Flash),宿主只捕获、触发、注入、召回。
放弃的是零 key 安装与「写入留在宿主 transcript」;换来的是三宿主同一套抽取、覆盖率不随宿主模型漂移。
可见性改由 dream-report、provenance 指针与 git 承担。

**Amendment (2026-09-04)**: 执行器成为库内置 agent:缺省 Vertex 项目与位置写进 config(`tigerless-seo` /
`global`,已实测可达),环境变量可覆盖;编排参考 OpenViking 的抽取循环——预取、逐轮「工具或操作」、
轮数上限、末轮强制交回、修复回合。工具由库执行,模型只做判断,核心零客户端不变。
