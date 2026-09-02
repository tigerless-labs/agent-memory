# ADR-006: 写入策略不拍板,由实验裁决

**Status**: accepted (2026-09-01)

**Context**: 边界蒸馏(hindsight)优于实时写入无对照证据;fork 的 cache 收益、
冷蒸馏的质量折损、阻塞成本的实际大小全部未测。调研中各家各执一派
(claude-mem 钩子 / MemCLI 自觉 / auto-memory inline)。

**Decision**: W0–W4 五选项(空白对照/边界自写/边界 fork/异步借力/inline)做成
实验变量;R 全程固定使 benchmark 得分差归因于 W;P2 在 Claude Code 上全选项对决,
产出默认档。记忆规则(skill 措辞、参数)同为被优化变量。

**Consequences**: 好——默认档有数据背书;实验系统沉淀为 CI 回归套件。
坏——v0.1 出厂前多一轮实验成本;各宿主可跑选项不同,结论跨宿主外推有边界。

**P2 首轮裁决(2026-09-01,n=24/臂,evidence: experiments/results/p2-longmemeval.md)**:
记忆净贡献成立(W1/W2/W4 对 W0 配对显著,零回退);W1/W2/W4 之间在此 n 下不可分,
故默认档 **W2** 按成本裁定(与 W1 同分、阻塞时长 141s → 0s),非按得分。
W3 待查:写得最多、分最低、唯一在弃权题上倒退。
