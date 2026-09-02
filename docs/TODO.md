# TODO

- [ ] ADR-007 实现语言待 Ryan 签字(见 decisions/adr-007)
- [x] Hermes 接入已核验:`hermes -z` 一次性模式、`-t` 限定 toolset(必须排除内置 memory)、
      `--provider` + `--model`;驱动已实现,阻塞点仅剩凭证(见下条)
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
- [x] single-session-preference 类的低分一半是判分问题:gold 是「好答案该满足什么」的细则
      而非答案本身,judge 需要第三条分支(已加,标定 23/25)
- [ ] **实验设计下限**:考试阶段独立重放同一批 store 同一配置,120 题上摆动 ±7。
      任何读侧/写侧结论都必须建立在「重复重放 + 配对」之上,单轮对比无论 n 多大都不可信
      (evidence: experiments/results/p2-optimisation.md,P5 两次重放 71 vs 57)
- [ ] 宿主失败原因被吞掉:`claude -p` 撞额度时把提示打到 stdout 并以 exit 1 退出,
      harness 只留 stderr,于是 runs.jsonl 里 error 为空、只剩 status=failed
      (fx1 110/120、fx2 120/120 即此因)——非零退出时应保留 stdout 尾部,
      并对「额度/限流」类失败停跑而不是把整轮跑成 failed

## 设计-实现一致性核对(2026-09-02)欠账

- [ ] 睡眠一次一 git commit:manage.md 明写「git 一睡眠一 commit」,Manage 未实现,
      dream-report 落盘但不入版本历史——审计链缺一环
- [ ] T1 提案的呈现路径:提案只进 dream-report,没有「下次 session 呈用户确认」的通道
- [ ] `mem gc`:cli.md 列了清理提案端点,未实现
- [ ] Docker 镜像(roadmap M5):未实现,MCP/CLI 同体分发缺一块
- [ ] `sessions/` 实际存明文 .txt,storage.md 原写「压缩副本」——已按实现改文档,
      压缩本身仍是待办(千条规模下体积是真成本)
- [ ] Hermes 跑不起来:唯一缺口是推理凭证。两条路择一——
      (a) `gcloud auth login`(账号 server@tigerless.com,需 aiplatform.endpoints.predict 权限),
          再走 Vertex 的 OpenAI 兼容端点;注意 hermes 的 custom provider 只从 config.yaml 读
          api_key,不读环境变量,而 gcloud token 一小时过期——这条路要么给 hermes 加 env 支持,
          要么用服务账号长期密钥;
      (b) 直接在 ~/.hermes/.env 设 GEMINI_API_KEY(AI Studio),`--provider gemini`,绕开
          gcloud、Vertex 权限与 token 过期。推荐 (b)。
- [ ] fx1/fx2(fixed-exam 两轮)无效:宿主调用非零退出且无 stderr,手工重放同样 prompt 正常,
      判定为环境性失败(疑似长时间连跑后的限流)。结论未取得,需重跑。

## Artifact 覆盖缺口(2026-09-02,见 docs/design/artifact-conformance.md)

- [ ] **staleness 净值曲线仍未测**:单轮 T0 在当天写的库上已测为中性(77 vs 79/76,
      evidence: experiments/results/p2-optimisation.md#p7),但那是**范围内的零**——
      库没有历史,M 无事可管。真正的度量需要纵向协议(session/recall/sleep 交替推进模拟时间),
      即设计里 MemGym 那一档,回放驱动器尚不支持
- [ ] **可证伪声明未进设计树**:artifact 明写「曲线为负 → 第 3 层应被砍掉」,
      manage.md 需补上这条,否则 M 是不可反驳的
- [ ] **闭环矩阵未进设计树**:13 组件 × 谁建/谁养/谁用的自检表,
      artifact 用它修过一次断链;现在新增组件(原料 FTS、.state)无处登记
- [ ] **写入率对照实验**:关/开钩子层数漏记条目,目前只有随跑遥测
- [ ] `feedback` 类型域:artifact 列了五类,设计树与实现只有四域
- [ ] UserPromptSubmit 自动查询注入:检索轨升级为确定性的那条可选路径
- [ ] 文件边界公理推论⑤软配额 / ⑥append 只属 archive / ⑦整页 topic file 反面教材
