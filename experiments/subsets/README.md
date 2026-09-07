# 冻结 Store 分层增量准备

本页保留第一步准备时的能力核对和接口设计；当前已实现的增量 CLI、结果结构及同步方案见 [incremental-runner.md](incremental-runner.md)。下文“当前 Harness 能力”和“尚未实现”描述的是第一步时点。

本目录只准备题目，不启动模型、Judge 或 benchmark。三个实验臂 Baseline、Progressive Read、Virtual Overview 必须读取同一份 [manifest](p4sup-seed20260901.json)，不各自抽样。本次未实现策略或 runner。

来源选择：仓库 `experiments/README.md` 的保留清单将 `experiments/runs/p4sup/stores` 标为 P5–P9 读侧实验共同使用的 120 份冻结真源，因此本计划固定使用其 W2 目录，不混用 p10am、p10mc 或睡眠后的 Store。

原始 suite 是 `experiments/data/longmemeval_s12.json`，含 500 题，已限制为每题最多 12 个 session。现有 `dataset.load()` 读取 question_id/question_type、问题、答案、日期、sessions 和 evidence。冻结 120 题来自该 suite 的 `stratified(..., 20, 20260901)`，已逐项核对源 runs.jsonl 的 ID/type、120 个 Store 目录及历史 episode fingerprint `213e6dcab30264e7`。`_abs` 保留为完整独立 ID，不另分桶。

| question_type | 冻结题数 |
|---|---:|
| knowledge-update | 20 |
| multi-session | 20 |
| single-session-assistant | 20 |
| single-session-preference | 20 |
| single-session-user | 20 |
| temporal-reasoning | 20 |

现有 sampling.stratified 已按 SHA256(`seed:question_id`) 桶内排序取前 N，再按 `(question_type, id)` 返回；相同 seed 下集合嵌套成立，但返回列表不是扩容前缀。本脚本通过现有 sampler 的逐级前缀恢复完整固定顺序，不修改 sampler，不引入第二个随机算法。全局顺序按桶内排名轮转六桶，stage 累计列表也是严格列表前缀。

| 阶段累计 | 每桶累计 | 本阶段新增（每臂） | 三臂新增总数 |
|---:|---:|---:|---:|
| 12 | 2 | 12 | 36 |
| 24 | 4 | 12 | 36 |
| 48 | 8 | 24 | 72 |
| 96 | 16 | 48 | 144 |
| 120 | 20 | 24 | 72 |

完整桶内顺序见本文末尾和 manifest 的 `bucket_orders`；`stages[].added_question_ids` 是增量调度输入，`cumulative_question_ids` 是累计汇总过滤输入。不得通过重新调用采样器替代读取 manifest。

## 离线生成与验证

在仓库根运行（使用现有 Python 环境，无依赖安装）：

```sh
.venv/bin/python experiments/subsets/prepare.py --check
.venv/bin/python -m pytest tests/system/test_subset_manifest.py -q
```

首次生成命令为 `.venv/bin/python experiments/subsets/prepare.py`；使用排他创建，不覆盖已有 manifest。复现到新文件可加 `--output /tmp/p4sup-subset.json`。不同 HEAD 的生成文件会记录新 revision；`--check` 保留原准备 revision，对源代码哈希及其他全部字段重算比较。生成时间未写入，以保持确定性。

manifest 包括 suite/源记录的 SHA256、每题完整 Episode 内容 SHA256、每份 Store 文件清单及内容 SHA256、整库真源摘要、准备代码 revision 和源文件哈希、自身摘要（去掉 manifest_sha256 字段的 canonical JSON）。canonical JSON 为 sort_keys=True、separators=(',', ':')、ensure_ascii=False 的 UTF-8。Store 真源范围是 `git ls-files` 列出的文件；按仓库约定不包含可重建索引、缓存或运行态。未跟踪文件不属于本计划真源，后续运行必须避免它们影响输入。旧 16 位 episode fingerprint 仅涵盖有序 ID，不能证明题目内容或 Store 一致；累计 fingerprint 按现有 Harness 返回顺序计算，不能用轮转列表替代。

## 当前 Harness 能力与限制

- `mem-exp run --per-type` 默认 4，`--seed` 默认 20260901；每次从 suite 分层选题。没有指定 question IDs 或 subset manifest 参数。
- `--resume` 有成功跳过：`_resumable()` 用 `(arm, episode_id)` 排除 status=ok（答错但成功判分也算完成），失败记录被移除再重跑。它要求 episode fingerprint/system 相同。
- `RunMetadataSink.ensure()` 要求 run.json 完全相同，包含 host/model、judge host/model、完整 config、code revision、Store 路径、exam mode、题集指纹等。12 扩到 24 会被拒绝；不能直接增加 per-type 配合 resume。
- 当前 metadata 未完整锁定 Store 字节、suite 内容、dirty code、prompt 内容、Host 二进制版本、exam_max_turns 等。路径或 HEAD 相同不足以保证完整实验一致。p4sup 历史记录没有 run.json，不能直接 resume，也不能纳入本次新实验累计成绩。
- `report --workspace` 只读单个 workspace；`report.summarise(records)` 可复用聚合函数，但没有跨阶段读取、按配置去重或累计 ID 过滤。直接拼接记录会重复计数，多个阶段的 episode fingerprint 也会使现有归因守卫失败。
- `--reuse-stores` 跳过 experience，但 Driver 直接使用源路径，并非只读快照接口；prepare、读访问日志等可能写入运行态。以后必须先解决运行副本/隔离与源哈希校验，不能把本次原始冻结目录当作可写运行库。本次未复制或修改任何 Store。

## 后续最小增量执行约定（接口设计，尚未实现）

1. 增加 manifest + stage 选择入口，例如 `--subset-manifest PATH --stage 24`，验证 manifest 及真源后解析新增 IDs，从现有 dataset 按 ID 查找 Episode，保持 manifest 顺序。禁止同时重新 per-type 抽样，所有实验臂共用同一 manifest。第一阶段取 12；之后只取新增 12/24/48/24。
2. 在现有 Driver、MetricsSink、成功跳过逻辑之上增加实验版本 sidecar 和任务筛选层。逻辑实验臂名与 W2 写入臂分开记录，不能把三个策略都记成不可区分的 W2。每条结果以 `(experiment_version, replay_id, arm, full_config_sha256, question_id)` 标识；完整原始结果持久保留，失败尝试另留，不覆盖成功结果。默认一个 replay；独立重放另用 replay_id，不能跨重放去重。
3. full_config_sha256 对完整规范化配置计算：manifest 摘要、suite 内容、源 Store 真源摘要、精确代码 revision 加 dirty 内容摘要、Host/客户端版本、实际 model 和推理参数、Judge Host/model/版本/投票数/解析规则/rubric、所有 prompt 模板及注入/工具设置、完整 Memory config、策略版本、exam mode/max turns、超时、环境和评测口径。显式锁定默认值，未知条件不能当作相同。stage 不进入配置身份，否则扩容不能复用；stage ID 列表单独记录。各臂自己的配置跨阶段不变，臂间只允许预先声明的策略差异。
4. 调度 `pending = stage.added_question_ids - 当前配置与当前臂已成功的 IDs`。阶段中断时继续同一阶段，已成功的不再调用 Host/Judge；扩容前检查上一阶段完整，缺失/失败先补齐。配置不一致的历史成功记录不能使新任务跳过。
5. 汇总层读取该实验版本各阶段既有与新增结果，严格按累计 ID 列表和配置筛选、去重，验证每臂恰好覆盖目标集合；缺失/失败显式报告，冲突成功记录报错。然后复用 `report.summarise()` 的统计，累计集合 fingerprint 放在汇总产物中，保留原始记录的阶段 fingerprint，不伪改旧记录。策略比较的归因需显式核对控制变量，不能依赖原 W 对比的单 recall 指纹守卫。
6. 改被测策略、代码、Host/model、Judge/rubric/prompt、Store 或评测口径时另建实验版本；不把不同条件旧结果混入累计。Judge 改动如需重判，应写入新版本，不能原地 regrade 后与旧分数拼接。

本次到此为止；以上参数是待实现设计，不是当前可执行命令。小阶段用于逐步扩展检查，不自动构成实验 ledger 结论。

## 每桶固定顺序

每行从左到右为第 1–20 题，切点依次为 2、4、8、16、20。

- **knowledge-update**：`7e974930`, `603deb26`, `618f13b2`, `72e3ee87`, `031748ae`, `2133c1b5_abs`, `b6019101`, `0ddfec37`, `f685340e`, `5831f84d`, `f9e8c073`, `8fb83627`, `41698283`, `6aeb4375`, `db467c8c`, `0e4e4c46`, `6aeb4375_abs`, `2698e78f`, `4b24c848`, `9bbe84a2`

- **multi-session**：`a96c20ee_abs`, `3a704032`, `09ba9854`, `67e0d0f2`, `d3ab962e`, `2311e44b_abs`, `e831120c`, `92a0aa75`, `aae3761f`, `3fdac837`, `4f54b7c9`, `09ba9854_abs`, `ef66a6e5`, `6d550036`, `d682f1a2`, `8e91e7d9`, `gpt4_5501fe77`, `gpt4_d12ceb0e`, `eeda8a6d_abs`, `eeda8a6d`

- **single-session-assistant**：`ceb54acb`, `41275add`, `7161e7e2`, `488d3006`, `cc539528`, `7e00a6cb`, `3e321797`, `e8a79c70`, `71a3fd6b`, `70b3e69b`, `778164c6`, `89527b6b`, `8aef76bc`, `6222b6eb`, `2bf43736`, `1d4da289`, `e982271f`, `1b9b7252`, `561fabcd`, `58470ed2`

- **single-session-preference**：`caf03d32`, `195a1a1b`, `1d4e3b97`, `1da05512`, `505af2f5`, `1a1907b4`, `95228167`, `06f04340`, `b0479f84`, `75832dbd`, `06878be2`, `32260d93`, `a89d7624`, `0a34ad58`, `1c0ddc50`, `54026fce`, `d6233ab6`, `b6025781`, `75f70248`, `8a2466db`

- **single-session-user**：`15745da0_abs`, `37d43f65`, `1e043500`, `6f9b354f`, `c960da58`, `19b5f2b3_abs`, `c5e8278d`, `d52b4f67`, `8ebdbe50`, `001be529`, `c14c00dd`, `311778f1`, `95bcc1c8`, `af8d2e46`, `58bf7951`, `66f24dbb`, `ad7109d1`, `ccb36322`, `bc8a6e93_abs`, `15745da0`

- **temporal-reasoning**：`gpt4_7abb270c`, `gpt4_2d58bcd6`, `gpt4_7a0daae1`, `2ebe6c90`, `dcfa8644`, `gpt4_7ca326fa`, `8077ef71`, `gpt4_70e84552_abs`, `2c63a862`, `982b5123`, `gpt4_85da3956`, `gpt4_21adecb5`, `gpt4_f420262c`, `0bc8ad92`, `gpt4_7bc6cf22`, `gpt4_0b2f1d21`, `gpt4_1a1dc16d`, `gpt4_2487a7cb`, `gpt4_fe651585`, `gpt4_b5700ca9`
