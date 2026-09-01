# ADR-002: 库核心零 LLM,智能从消费端借用

**Status**: accepted (2026-09-01)

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
