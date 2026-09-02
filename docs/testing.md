# 测试规范

> 状态 accepted;五类测试及通过线。前三类每次变更必跑;压测按 release;红队上线门前必过。

| 类 | 范围 | 通过线 |
|---|---|---|
| 单元 | 核心库各模块(管线、水位线、边界规则、评分) | 行覆盖 ≥85%,分支 ≥75%,低于 CI 红 |
| 系统 | CLI/MCP/钩子三入口一致性;并发写;重建等价 | 关键路径全绿 |
| E2E | P1 冒烟脚本:三宿主接入 → 写 → 读 → 互通 | 全绿 |
| 压测 | 千条记忆下 recall p95、索引增量耗时 | 预算写入 config 并断言 |
| 红队 | poisoning payload、恶意 frontmatter、注入-经-召回、并发损坏 | 全部 fail-safe |

约定:
- **Fixtures 不打真服务**:宿主用回放桩;benchmark 用抽样子集固定 fixture。
- **断言关系与不变量,不断言硬编码值**(如「重建前后 recall 结果集合相等」,
  而非具体分数)。
- 每个 roadmap 环节先写失败测试再实现(TDD);测试映射表随实现补充于此。

## Per-file test map

| 实现模块 | 测试 |
|---|---|
| `core/config` | `tests/unit/test_config.py`(默认值、往返、未知 knob 拒收、魔数扫描) |
| 包结构 / 依赖纪律 | `tests/unit/test_packaging.py`(core 零依赖、无模型客户端、导入冒烟) |
| `core/record`·`core/frontmatter`·`core/slug`·`core/archive`·`core/store` | `tests/unit/test_storage.py` |
| `core/indexer`·`core/manifest`·`core/search_index`·`core/memory_md` | `tests/unit/test_indexer.py` |
| `core/locking` | `tests/system/test_concurrency.py` |
| `core/recall`·`core/chunking`·`core/access_log` | `tests/unit/test_recall.py` |
| `cli/main`·`core/portability` | `tests/system/test_cli.py` |
| `core/watermark`·`adapters/*` | `tests/unit/test_write_triggers.py` |
| `core/manage` | `tests/unit/test_manage.py` |
| `mcp/server`·`mcp/tools`(三入口一致性) | `tests/system/test_entry_equivalence.py` |
| 红队(poisoning / 恶意 frontmatter / 越界写) | `tests/redteam/test_poisoning.py` |
| `harness/*`(回放驱动器、隔离闸、指标、报表) | `tests/system/test_harness.py` |

## 判分器是仪器,仪器要标定

benchmark 的 LLM judge 与被测系统同为变量:rubric 写歪会把正确行为判成错误
(实测:弃权题的正确答案是「拒答」,而初版 rubric 写着「拒答判错」)。因此:

- 手工标注用例集 `experiments/judge-calibration.json`(答对/答错/该拒答/不该拒答四类);
  `mem-exp calibrate` 跑一致率,rubric 或 judge 模型改动前后必跑。
- judge 单次调用有噪声,取多票多数;当前设置下一致率 ≈ 97%,即每 24 题约 ±1 的判分噪声,
  报表里的差值小于此即为噪声。
- `mem-exp regrade` 用存下来的答案离线重判——换 rubric 不需要重跑宿主。

