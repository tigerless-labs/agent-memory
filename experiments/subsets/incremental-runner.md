# Manifest 增量执行接入

只接入现有 `mem-exp run`、Driver、RunRecord、MetricsSink、RunMetadataSink 和 report.summarise；不改变 Memory/Observation/Judge 算法，不重新抽样。固定来源仍为 [p4sup manifest](p4sup-seed20260901.json)，其内容和指纹未变。

## 分支核对（实现前）

| 分支 | 实际本地 HEAD |
|---|---|
| exp/shared-eval-base | bbfb2aae95c882bc6c4905da23f99e29d972ddc8 |
| exp/progressive-read-baseline | bbfb2aae95c882bc6c4905da23f99e29d972ddc8 |
| feat/progressive-read-raw-trace | e9ff90e369f602f576da3381099e6550e21f055f |
| feat/virtual-topic-overview | e43252de1e8bbbda252cd3a86fe5bc0dc8d80b59 |

三个臂的 `packages/harness`、`packages/executor` 与 shared base 完全一致，包括 Driver、Observation、Judge、run.json 和 resume。Progressive 相对 base 仅 context/prompts、测试及文档有差异（7 文件）；Overview 的差异为 core overview/eligibility/recall/config/prompts、CLI、测试和 README（9 文件）。因此它们具备同一公共评测基线，但 Memory 行为和 feature revision 本来就不同，不能拼成同一实验臂累计。

实现分支 `feat/incremental-eval-runner` 从 shared base 新建。没有 rebase，没有修改 main 或三个实验臂分支。此核对基于本地分支，未访问远端或 fetch。

## CLI

以下是**后续真实执行时的用法，本次未执行**。在对应 feature checkout 根运行，Python/`mem` 必须来自同一 checkout；三个臂使用各自 workspace，并使用同一绝对 manifest 路径。`--reuse-stores` 指向含 W2 的父目录，而不是 W2 本身。

```sh
mem-exp run \
  --suite /home/codexlab/code/agent-memory/experiments/data/longmemeval_s12.json \
  --subset-manifest /home/codexlab/code/agent-memory/experiments/subsets/p4sup-seed20260901.json \
  --reuse-stores /home/codexlab/code/agent-memory/experiments/runs/p4sup/stores \
  --workspace /home/codexlab/code/agent-memory/experiments/runs/read-v1-r1/baseline \
  --experiment-version read-v1-r1 --experiment-arm baseline \
  --arms W2 --stage 12 --run-id baseline-12 \
  --host codex --model gpt-5.6-sol \
  --judge-host codex --judge-model gpt-5.6-sol --concurrency 1
```

由 12 扩到 24：保留以上全部实验条件及 workspace，仅把 `--stage 12` 换成 `--stage 24`，`--run-id` 可以换成 `baseline-24`。只调用新增 12 题。随后 48/96/120 分别新增 24/48/24 题。重复调用同一命令自动跳过所有已经成功的题；manifest 模式无需 `--resume`，加上它也保持同样幂等行为。上一阶段有缺失/失败时，扩容拒绝，先再次运行上一阶段补齐。

可加 `--question-ids ID1 ID2 ...`，只执行当前 stage 的新增 ID 中指定的部分；必须属于 added_question_ids，不重新排序抽样。部分执行后累计仍缺题会返回 1，报告列出 missing_question_ids。manifest 模式中的 per-type/seed 不参与选择；不要给它们传采样参数。

普通旧 CLI 也支持 `--question-ids ID1 ID2 ...`，按指定顺序取题；不指定时仍使用原 `--per-type`/`--seed` 默认值和 stratified。旧同题集 `--resume`、旧 run.json 的比较和兼容行为不变。普通模式不可写入增量 workspace 或它的 stage 目录。

新增模式目前仅支持本次原生冻结 W2 读侧实验（`--system agent-memory --arms W2`）；逻辑实验臂由 `--experiment-arm` 区分，不冒充 W0/W1 等写入策略。独立重放另建 experiment-version/workspace，例如 read-v1-r2。

## 持久化与执行隔离

```text
<workspace>/                         # 一个 experiment version + 一个逻辑臂
  experiment.json                    # 稳定实验身份和全部公共/特征来源信息
  subset.json                        # 原 manifest 的不可变本地快照，语义摘要完全相同
  .incremental.lock                  # 执行/报告互斥；进程退出自动释放锁
  stages/
    12/
      run.json                       # 复用原 RunMetadata 格式，固定本阶段题集 fingerprint
      questions.json                 # 本阶段完整 added IDs -> question
      invocations.jsonl              # 当前 run-id、stage、待执行 IDs、实际源路径、身份摘要
      runs.jsonl                     # 原 RunRecord 字段 + identity_sha256，保留成功/失败尝试
    24/ ...                          # 不覆盖阶段 12 的文件
```

每条结果完成即落盘，JSONL 原子替换避免进程中断留下半行。恢复只跳过 status=ok（答错但已成功判分也跳过）；failed 不计成绩，重试仍保留旧尝试。完全相同的重复成功记录只计一次，有冲突的成功记录拒绝汇总。进程被杀前尚未持久化的调用不能证明完成，恢复时会重试；不声称外部模型调用具有事务性 exactly-once。锁防止同一 workspace 的两个进程同时调度同一题。

每次先按 manifest 校验 suite、每题内容、Store 真源文件及整库摘要。实际执行时仅将 pending IDs 的 manifest-listed 文件复制到 stage 下的临时运行目录；不复制索引、未列出的文件或源运行态。副本的 config.toml 写入本次完整配置（使 Host 的 mem CLI 与 Harness 使用一致配置），复用现有 Indexer 重建本地缓存；不重写冻结 MEMORY.md。Driver/Host 只接触副本，每次重试重新从冻结真源开始。退出后删除临时副本；源真源复核，逐题 Observation 留在结果记录。未运行真实数据时不会创建真实 Store 副本。本次仅 Fake fixture 使用此路径。

## 实验身份

`experiment.json` 锁定以下条件，每条记录的 identity_sha256 绑定其完整内容：

- experiment-version、experiment-arm、同一 manifest 摘要与 Store 真源摘要；
- 实际 feature HEAD，以及当前 checkout 全部 packages/*/src Python 文件的 SHA256 清单和摘要，包含未提交源码；
- 独立 `harness_sha256`：Harness + Executor + 公共 access_log 源码内容摘要；跨 feature 分支可保持相同，不用不同的 feature HEAD 假装 Harness 版本不同；
- Host/Judge 的完整 HostSpec（实际 model、provider、超时、重试），可执行入口文件摘要；
- Judge rubric、投票数；Judge 解析/计分实现由共同 Harness 源码摘要锁定；
- 全量 Memory config（含 Read/Recall）、system、exam mode/max turns、manage 和 concurrency；prompt 模板由源码清单锁定。

stage、run-id、workspace、运行副本路径不进入行为配置身份。源路径也不代替真源摘要：另一个路径上的逐字节相同真源可复用；实际源路径记入 invocation。stage 保有自己的 episode fingerprint；扩大集合通过 manifest 的合法 added/cumulative 关系校验，绝不绕过旧 resume 指纹守卫。run.json 中 run_id 是该 stage 首次 invocation 标签，后续 invocation 的 run-id 在逐题结果和 invocations.jsonl 中。

feature HEAD、任何源码内容、Host/model、Judge/rubric、Memory 配置变化，同一 workspace 拒绝启动，必须建立新的 experiment-version/workspace。报告不依赖当前 checkout 的版本，因此可以离线查看历史版本，但会交叉核验历史身份、每阶段 run.json、行级身份和题集。禁止对增量结果原地 regrade；改 Judge 需新版本。Host 后端的隐式模型更新/客户端入口外的依赖不可能仅由本地文件摘要证明一致，应固定部署环境并在发生这些变更时主动换实验版本。

## 累计汇总

```sh
mem-exp report \
  --workspace /home/codexlab/code/agent-memory/experiments/runs/read-v1-r1/baseline \
  --stage 24 --json
```

读取 workspace 的固定 subset.json、experiment.json 和各 stage 的旧、新记录。按累计 ID 过滤、成功去重，复用 report.summarise；报告给出 completed、missing_question_ids、complete、累计 fingerprint、总分和各桶结果。完整返回 0，缺失/失败未补齐返回 1。即使已扩到 120，也可分别 `--stage 12/24/48/96/120` 回看各累计样本。可用普通 shell 重定向保存 JSON；报告命令不调用 Host/Judge。

原始记录中的阶段 episode fingerprint 不修改，仅经过身份/题集校验的内存汇总视图使用 manifest 的累计 fingerprint。不同逻辑臂不能拼在同一 workspace；此接入只提供每臂累计汇总，不新增跨臂显著性分析或突破既有实验规范的归因结论。比较三个臂时核对相同 manifest、Harness/Judge/Host/Store 和其他控制条件，只允许声明的策略差异；不要把各臂结果直接 cat 进旧 report。

## 公共实现同步的最小方案

本分支保留两笔本地提交：第一笔纳入上次准备的固定 manifest/脚本/说明/测试；第二笔是本次公共 Harness 接入、离线测试与使用说明。后续对 Baseline、Progressive、Overview 分别按序 cherry-pick 这两笔（若已含第一笔则只取第二笔），不需要重新 rebase，也不需要改 main。三个臂的 Harness 路径原本无差异，因此公共实现可保持逐字节相同；同步后复核 `packages/harness`、`packages/executor`、`core/access_log.py` 无差异，分别运行相关离线测试，再冻结新的三个 feature HEAD。每臂拥有自己的 feature revision；公共 harness_sha256 应相同。

本次没有执行同步、push、merge 或正式实验。所有新增执行测试均使用 Fake Host/Fake Judge transport、离线小 Store fixture；真实 manifest 只做只读校验。

## 本次验证记录

- 增量离线测试 15 项通过：五阶段扩容、重复调用、失败/中断补跑、配置/Judge/rubric/revision 变化拒绝、三臂同 manifest、去重冲突、旧显式 ID resume、锁、真源校验、真实 fixture 检索与有效配置。
- 全量 `pytest -q --cov=agent_memory --cov-report=term --cov-fail-under=85`：370 passed，覆盖率 92.68%。
- `ruff check .`、`mypy packages`、`prepare.py --check` 通过。
- 原 prepare.py 已被固定 manifest 逐字节指纹锁定，因此保留其原字节，仅在 Ruff 配置中对该历史脚本的 E501 长行规则做窄范围豁免；抽样顺序和 manifest 均未重写。
