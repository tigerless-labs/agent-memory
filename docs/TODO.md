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
- [ ] **W3 的负面结论已被自己的记录推翻,两处文档待改**:标定后重判的 runs.jsonl 给出
      W3 = 8/24(p2)与 8/24(p2v2),弃权题 2/2;与 W1/W2/W4 两两配对 p=0.51–0.73,全部不可分。
      「写最多分最低、唯一在弃权题上倒退」出自标定前的旧 rubric(旧 rubric 把拒答一律判错,
      本就分不出此事)。p2-longmemeval.md 的 headline 表与本行原文均需按记录订正;
      W3 现有证据只支持「写得最多」,不支持分数更差
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
- [x] **实验设计下限已成文**:重复重放 + 逐对配对、n≥120、禁止跨重放取多数,
      连同实验分类、归因条件、run 必留项、失败处理,落在 docs/experiments.md,CLAUDE.md 已引用
- [x] 宿主失败原因不再被吞掉:非零退出保留 stdout 尾部;`mem-exp run` 撞到额度/限流类失败即停
      (已测记录保留,其余不记),`--resume` 只补跑未成功的题(同 episode 集、同系统才允许)

## 设计-实现一致性核对(2026-09-02)欠账

- [ ] 睡眠一次一 git commit:manage.md 明写「git 一睡眠一 commit」,Manage 未实现,
      dream-report 落盘但不入版本历史——审计链缺一环
- [ ] T1 提案的呈现路径:提案只进 dream-report,没有「下次 session 呈用户确认」的通道
- [ ] `mem gc`:cli.md 列了清理提案端点,未实现
- [ ] Docker 镜像(roadmap M5):未实现,MCP/CLI 同体分发缺一块
- [ ] `sessions/` 实际存明文 .txt,storage.md 原写「压缩副本」——已按实现改文档,
      压缩本身仍是待办(千条规模下体积是真成本)
- [x] Hermes 已跑通:Vertex OpenAI 兼容端点 + gcloud token(harness 按需签发、到期前续),
      provider 用 `gemini` 并把它将要剥掉的 `<provider>/` 前缀补回去。原方案记录如下——
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
- [ ] 跨宿主写入量差 13×(hermes 2.8 / claude 6.2 / codex 36.8 条每 episode,
      指令与题目完全相同;evidence: experiments/results/p1-generality.md)——
      这是对「agent-agnostic」前提的直接威胁。先分清是服从度、turn 预算还是接口摩擦
      (每条 `mem record` 占一个 turn),三者的解法分别是 prompt、配置、批量写入 API。
- [ ] `HERMES_MODEL` 走 Vertex 时必须是 publisher 限定的(`google/gemini-3.7-flash`);
      项目 .env 里现存的裸 id 会被端点拒。
- [ ] `recall.default_limit` 已退回 8:改 24 的依据(p6)把列表宽度与考试模式一起变了,
      清洁对照下四组重放配对 p=0.36/0.12/0.63/1.00 且方向会翻(evidence: p6-list-width.md 已改为撤稿)
- [ ] **考试模式不在 recall fingerprint 里**——归因守卫看不见这一轮里最大的那个变量。
      exam 形态(fixed / agentic)应进指纹,否则它拦不住它本该拦的比较
- [ ] 「跨重放取多数」在两轮臂上实为并集(任一轮答对即算对),会同时抬高两臂并偏袒方差大的那一臂;
      P6/P8/P9 用过该聚合,结论需按逐对配对检验复核(P6 已复核并撤稿)
- [ ] recall fingerprint 不能跨 config schema 变更反解:加/移 knob 会改变所有 fingerprint,
      旧运行的配置无法用当前 config 空间搜回来(`1c553b61`、`361ded7e` 即如此)。
      守卫仍能拒绝错误归因,但不能当作「那一臂当时是什么」的记录——配置要写进 write-up。

## 今日核对新增(2026-09-02)

- [ ] **MCP 缺 `memory_context`**:P9 的 write-up 称收益「CLI + MCP 同体,每个宿主都够得着」,
      实际 mcp/tools 只暴露 recall/read/record/correct/feedback。`--batch` 同样只在 CLI。
      唯一复现成功的读侧结果,走 MCP 进来的宿主拿不到——直接违反不变量 8(异入口同结果)
- [ ] `recall.context_full_text_entries = 4` 从未被任何 run 变过(只有一个单元测试设成 1)。
      它决定 context 里几条展开全文,是纯读侧、可用重放廉价测:4 / 8 / 全摘要三档 × 两次重放
- [ ] 对照臂候选:obsidian-second-brain(eugeniughelbur)与 obsidian-mind(breferrari)同属
      「markdown 真源 + Claude Code 钩子」一族,写入决策同样落在消费端。前者有读侧 eval
      (300 篇合成语料 / 48 问 / recall@k + MRR,单跑无重放),其 BASELINE.md 自陈不测写入覆盖;
      后者无任何评测。若做系统对照,覆盖率探针是唯一能分离两系统的量
- [ ] `_propose_merges` 是 O(n²) 两两 Jaccard,全量每睡一次。小库无感,需要给出规模上界
      或加分桶预筛(共享 token 倒排)后再谈大库
- [ ] T0 允许推理者重写摘要,于是被策反的推理者能把攻击者文字写进摘要(长度超限会被 frontmatter
      校验挡下,正常长度不会)。目前只靠 dream-report + git 可见可回滚。是否需要「替换摘要必须与
      该条正文有词汇重合」之类的写入侧判据,待定——先别拍脑袋加启发式
- [ ] 提案没有条数上限:合并候选带一放宽(0.75 → 0.35,提案 10 → 132),一次睡眠的提案会
      随库变大而线性增长,而 render 把全部提案与被点名条目塞进同一个 prompt。大库上会超长。
      需要 `manage.max_proposals_per_sleep`(按相似度取前 N),而不是靠阈值兜着
- [ ] 合并候选带本身待定:0.75 是仿真值,实测在 3600 条真实条目上只出 1 条 merge 提案;
      0.35 出 132、0.25 出 378。哪一档该是默认,取决于 P11 里推理者的否决率——先测再定
- [ ] write-up 里凡给 M 的分数,先给「触及率」:这次睡眠改动过的考题占比。P11 里 24 题只有
      6 题被动过,也就是说这一轮最多只能看见 6 题的差异——这个上界必须和分数一起写出来,
      否则供能不足会被读成负结果(evidence: experiments/results/p11-manage.md)。
      就地算,别做成报表子命令
- [ ] 纵向协议(session 批 → 睡眠 → session 批 → 睡眠 → 考试,批次间推进时钟)仍不存在。
      没有它,M 的立身之本(陈旧、被取代的值、话题密度)在实验里根本不出现
- [x] **覆盖率探针已进 harness**:`mem-exp coverage` 离线按(系统, W)报答案落盘率;
      历史实测(p4sup 冻结语料,110 可答题)答案落进某条记忆的仅 36/110 = 33%,而这 36 条里
      recall top-8 捞回 34(94.4%)——检索不是瓶颈,写入覆盖是
- [x] 与 MemCLI 的对照实验(P10,同宿主 Claude Code,带 W0 对照)已完成:agent-memory 127/240
      对 MemCore 86/240,两次重放逐对 +37/−17(p=0.009)与 +35/−14(p=0.004);写入覆盖率
      32/110 对 37/110,差距不在落盘而在其后(evidence: experiments/results/p10-memcore.md)
- [ ] P10 后续(读侧,重放 p10mc 冻结库即可):给 MemCore 的考题前言加上 synthesis 段,
      看 knowledge-update / multi-session / temporal 三类的差距是否由前言驱动
- [ ] 写前「先 recall / supersede」纪律从未被单独裁决:P4 触发 25 条边、得分 9/15 = 9/15,
      而每次 mem 调用占一个 turn(P1 的 13× 写入量差);需一轮写侧全跑:W2 去掉该段 vs 保留

## schema 驱动写入(2026-09-03,plan: docs/plans/schema-driven-write.md)

- [ ] **实验(计划第 7 单元的后半)未跑**:需要 Vertex 凭据与纵向协议。三项待跑,均按 docs/experiments.md:
      (a) 写侧全跑 W3(库侧执行器,缺省)对 W1(宿主自写):`mem-exp run --arms W1,W3`,R 固定,n ≥ 120,两次重放;
      (b) `--set write.slot_table=false` / `--set write.event_lane=false` 两臂对缺省,先看覆盖率探针再看分数;
      (c) M on/off:同一批库拷贝后 `mem-exp sleep-stores`(缺省推理者=执行器)再考,纵向协议先落地才有 staleness 净值
- [ ] MCP `memory_decide` 只能带 `text`:接受 merge / split 需要 abstract、body、parts,
      目前只有 CLI `decide` 能给;补 MCP 参数,否则违反不变量 8
- [ ] 旧四域布局 → schema 布局的迁移命令与 config 版本号(接上面「config knob 改名」那条)
- [ ] abstract 缺省由键字段渲染、agent 可覆盖:两种写法对检索的影响需对照
- [ ] 出厂类型说明里明确重叠处谁赢(profile vs preference,entity vs reference)
- [ ] 事件通道对弃权稳定性的影响,与 `--deep` 削弱弃权那条一起测
- [ ] Gemini 3.7 Flash 的模型 id 与 Vertex 端点核验后写入 config 缺省
- [ ] artifact-conformance.md 的覆盖核对按 ADR-008 / ADR-009 重跑
