# Roadmap v0.1

> 状态:待开工(设计门已过:docs/design 全 accepted,ADR-007 待签)
> 依据:docs/design/index.md 全树;测试线见 docs/testing.md
> 每环节 = 一个分支 plan(docs/plans/<change>.md,AI 自主拟定执行);
> **每环节先写失败测试再实现(TDD)**,测试断言关系与不变量,不断言硬编码值。

## M0 · 脚手架与 CI

- 内容:uv workspace、包结构(core / cli / mcp / adapters / harness)、config 对象、
  CI(lint + 类型 + 测试 + 覆盖率线 + 「核心依赖禁 LLM 客户端」检查)
- TDD 测试:
  - [ ] config 加载与全 knob 默认值(config 之外 grep 不到魔数)
  - [ ] CI 冒烟:空库 import 全包通过;依赖清单断言不含模型客户端

## M1 · Storage 核心(真源 + 边界规则)

- 内容:域树初始化、frontmatter schema 与校验器、slug 稳定 id、archive 三格 append
- TDD 测试:
  - [ ] 合法/非法 frontmatter 校验(缺字段、坏日期、type 与域不符 → 拒收含结构化错误)
  - [ ] 文件边界规则:同 name 重写 = update;superseded_by 置值后旧条不出现在 active 集
  - [ ] archive append-only:模块无删除接口;provenance 摘录落盘且可按 id 取回
  - [ ] slug 稳定性:文件跨目录 mv 后 links/supersede 解析不断

## M2 · 索引管线(投影 + 重建等价)

- 内容:manifest content-hash 增量、FTS5 索引(abstract+正文,超长按 heading 多条)、
  MEMORY.md 索引行维护、links 目标校验、flock 串行化
- TDD 测试:
  - [ ] 增量性:改 1 个文件只重索引 1 个文件(manifest diff 断言)
  - [ ] **重建等价(Invariant 1)**:任意操作序列后删 .index/ 重建,recall 结果集合相等
  - [ ] 悬空 link 校验报警不拒收
  - [ ] 并发:两进程同时 record,flock 下无损坏、两条都在

## M3 · CLI + Recall 管线

- 内容:record/recall/read/correct/rebuild/sleep/inspect/export;资格过滤→BM25→
  评分(相关度×weight×时效)→L0 列表;--as-of / --deep / --scope;命中锚点与机械大纲;
  access log
- TDD 测试:
  - [ ] 资格先于相关性:superseded 条目默认不出现;--as-of 按 valid_from/supersede 链命中旧值
  - [ ] 字面检索:错误码/路径/专名类 query 命中(fixture 断言包含关系)
  - [ ] L0 列表契约:abstract+路径+锚点+分数字段齐全;--json 稳定 schema
  - [ ] **读不改真源(Invariant 3)**:recall 后真源文件 hash 全部不变,access log 有行
  - [ ] export 往返:export → 新盘 import → recall 结果集合相等(迁移成本指标的测试化)

## M4 · Write 触发层(水位线 + 钩子 + skill)

- 内容:水位线模块、Claude Code / Codex 钩子 adapter(停顿点/淘汰点/注入点)、
  setup 自安装、skill 文档(写前纪律)、sessions/ trace 归档开关
- TDD 测试:
  - [ ] 水位线幂等:同一 transcript 重复触发,蒸馏输入只含增量;kill 后补收覆盖尾巴
  - [ ] 钩子失灵无害:禁用全部钩子,cron 路径推进水位线,结果集合与钩子路径一致
  - [ ] 钩子异常不破坏宿主:钩子脚本超时/报错,宿主流程退出码不受影响
  - [ ] 注入轨:SessionStart 注入内容 = MEMORY.md 预算内前缀,逐字节断言
  - [ ] 三入口一致性(Invariant 8):同一 record/recall 经 CLI 与 MCP,结果相等

## M5 · MCP server + Docker

- 内容:五工具(recall/read/record/correct/feedback)映射核心调用;Docker 镜像
  (CLI+MCP 同体,-v 挂盘)
- TDD 测试:
  - [ ] 工具 schema 校验与错误码;超时行为
  - [ ] 容器内外等价:同盘经容器 MCP 与本机 CLI 操作,结果相等
  - [ ] 冒烟:docker run + 挂载盘 → record → 宿主侧文件出现且可 git diff

## M6 · 睡眠 M(T0 + dream-report;T1 提案)

- 内容:条件触发(≥24h 且 ≥N session)、T0 全操作、weight 结算、聚簇成目提案、
  dream-report + git 一睡眠一 commit
- TDD 测试:
  - [ ] T0 无删除:睡眠前后 active+archive 全集不减少(只增改断言)
  - [ ] 日期规范化与重复合并的幂等性(跑两次 = 跑一次)
  - [ ] weight 结算:构造 access log fixture,断言升降方向与三级降档顺序(可逆)
  - [ ] 聚簇提案:域根 ≥阈值同话题 fixture → dream-report 含建目提案;未确认不执行
  - [ ] 红队:poisoning 条目(prompt 注入文案)经召回呈现为数据;M 不因其内容改变行为

## M7 · 实验系统 P1(通用性冒烟)

- 内容:回放驱动器(经历/考试两阶段、隔离闸)、三宿主 headless 驱动
  (claude -p / codex exec / hermes)、指标采集器、小套件接入
- TDD 测试:
  - [ ] 隔离闸:考试会话构造的 prompt 中断言不含经历阶段 transcript 内容
  - [ ] 驱动器对宿主故障的重试与标记(宿主超时 → run 标 failed 不污染结果)
  - [ ] 互通:A 宿主写入 fixture → B 宿主 recall 命中(三宿主两两)
  - [ ] 指标 schema:每 run 产出结构化结果(得分、token、latency、写入遥测)可聚合

## M8 · 实验系统 P2/P3(写入对决 + 调优回路)

- 内容:LongMemEval-V2 + MemoryAgentBench 适配、W0–W4 选项开关、结果聚合报表、
  规则调优记录(每轮规则改动 = 一条 plan + 重跑核心子集)
- TDD 测试:
  - [ ] W 选项开关互斥且可从 config 复现(同 config 同结果集合,LLM 波动除外的机械部分)
  - [ ] 归因前提(Invariant 9):全部 W 选项 run 的 R 配置 hash 相同,断言拦截漂移
  - [ ] 回归子集:P2 核心子集一键重跑,报表对比上一轮(方向性断言)

里程碑门:M0–M6 每环节绿 CI 才进下一环;M7 P1 失败 → 返工接入层,不进 M8。
