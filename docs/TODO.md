# TODO

- [ ] ADR-007 实现语言待 Ryan 签字(见 decisions/adr-007)
- [ ] Hermes Agent 接入细节核验:provider 接口、运行日志格式、headless 驱动方式
- [ ] MemGym 任务形态与回放驱动器适配调研(P1 前置)
- [ ] 跨 agent weight 语义(A 常用对 B 是否噪音)——P3 后凭数据再议
- [ ] MEMORY.md 注入预算是否按 agent 分——同上
- [ ] 长文档型记忆检索面(reference 域整篇文章):摘要作检索面 + 目录级种子 + 分数传播(OpenViking 形)
- [ ] experience 域类型级生命周期差异(use_when/avoid_when,BASM 方向)——v0.2
- [ ] 重要性阈值触发(session 内中间档)——v0.2,P2 数据证明边界蒸馏漏隐式教训再上
- [ ] 实习生方案文献补进调研 atlas(TEPA/MemGate/BASM/AgeMem/M★/MemHarness 等 10 篇)
- [ ] Graphiti 引用 URL 勘误(getzep/graphiti,非 Agentopia)——通知实习生
- [ ] W3 冷读蒸馏在 P2 上写得最多、分最低,且是唯一在弃权题上倒退的臂
      (evidence: experiments/results/p2-longmemeval.md)——冷读缺少现场 context 的
      代价需定位后再作为 cron 兜底档
- [ ] P2 需扩大 n:W1/W2/W4 在 n=24 下不可分(两两 p ≥ 0.6),写入默认档暂按成本定为 W2
- [ ] config knob 改名/迁位会让旧 store 直接加载失败(严格拒收未知 knob 是故意的,
      但缺迁移路径)——需要 config 版本号 + 迁移,或 `mem inspect` 给出可执行的修复建议
- [x] P2 单臂 n 提到 120 完成确证:原料兜底对得分无影响(配对 +13/−14,p=1.000),
      而深检索把 gold 可检出率从 20% 提到 37%——瓶颈已在使用端
      (evidence: experiments/results/p2-optimisation.md)
- [ ] 深检索会削弱弃权:原料里够得着相关片段时,agent 更倾向编答案而不是说不知道
      (v4 弃权 1/2,v1 2/2)——渐进披露的最后一级需要「找到片段 ≠ 找到答案」的提示
- [ ] LongMemEval 上剩余损失在回答步而非记忆:gold 已检出仍答错 15/110、gold 未检出却答对 20/110
      ——需要「答题纪律」实验(检索次数、读全文 vs 只看 abstract、跨条目聚合),但这是宿主侧课题
- [ ] 弃权行为不稳定:同一配置下 5/10 与 7/10 之间摆动,渐进披露最后一级需要
      「找到片段 ≠ 找到答案」的显式提示
- [x] supersede 在实写中从未触发(3744 条记忆 0 条边)——根因是 API 形状而非纪律,
      已加 `mem record --supersedes`,机制恢复(120 store / 25 条边);
      但对得分无影响(触发的 15 个 episode 上 9/15 = 9/15)
- [ ] single-session-preference 类始终 5–15%:问的是「按我的偏好给建议」,
      需要的是把多条偏好合成一个回答,而非取回单条事实——现有评测面覆盖不到,先记着

