# API:CLI 面

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**

CLI 是 universal fallback(能跑 shell 的 agent 皆可用)与 operator/admin 面;
不含任何检索/写入算法(Invariant 8)。全命令支持 `--json`。

| 命令组 | 端点 | 作用 | 调用方 | 副作用 |
|---|---|---|---|---|
| 记忆 | `record` | 写入一条记忆(经管线校验+重索引) | agent | 写真源+索引+archive |
| | `recall <query>` | 检索,返回 L0 列表(abstract+路径+锚点+分数) | agent | 写 access log |
| | `read <name>` | 读单条(全文/`--outline` 大纲) | agent | 写 access log |
| | `context <query>` | 一次调用:检索 + 打开头部条目,返回可直接推理的上下文 | agent | 写 access log |
| | `correct` | update 或 supersede 一条 | agent | 写真源+索引 |
| 时序 | `recall --as-of <date>` | 时间点查询(沿 supersede 链) | agent | 同 recall |
| | `recall --deep` | 检索面扩到 archive | agent | 同 recall |
| admin | `rebuild` | 删索引后全量重建 | 人/CI | 重写 .index/ |
| | `sleep` | 手动触发睡眠 M(`--reason` 附带推理者) | 人/cron | T0 直改;T1 出提案 |
| | `proposals` | 列出待确认提案 | agent/人 | 无 |
| | `decide <id>` | 确认或否决一条提案 | agent/人 | 记入账本;确认时写真源 |
| | `inspect` / `gc` / `export` | 体检 / 清理提案 / 全量导出 | 人 | export 无副作用 |
| 安装 | `setup` | agent 读 setup 文档自接线(探测宿主→装钩子→验证) | agent | 写宿主配置 |

- **幂等**:`record` 以 name 为键可重放;`rebuild` 任意次等价。
- **错误模型**:校验失败返回结构化错误(字段+原因),agent 可自修复重试。
- **敏感**:export 全量含 archive,提示用户确认。
