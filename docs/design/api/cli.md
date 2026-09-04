# API:CLI 面

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**

CLI 是 universal fallback(能跑 shell 的 agent 皆可用)与 operator/admin 面;
不含任何检索/写入算法(Invariant 8)。全命令支持 `--json`。

| 命令组 | 端点 | 作用 | 调用方 | 副作用 |
|---|---|---|---|---|
| 记忆 | `record` | 写入一批记忆(动词 new / supersede / update / skip,句柄只能来自对账单;经管线校验+重索引) | agent | 写真源+索引+archive |
| | `distill` | 取水位线增量 → 渲染 → 对账单 → 库侧执行器填表 → 批量应用 | 钩子/cron | 写真源+索引+archive |
| | `trace <name>` | 按 provenance 指针打开该记忆的原始消息 | agent/人 | 写 access log |
| | `recall <query>` | 检索,返回 L0 列表(abstract+路径+锚点+分数) | agent | 写 access log |
| | `read <name>` | 读单条(全文/`--outline` 大纲) | agent | 写 access log |
| | `context <query>` | 一次调用:检索 + 打开头部条目,返回可直接推理的上下文 | agent | 写 access log |
| | `correct` | update 或 supersede 一条 | agent | 写真源+索引 |
| | `delete <name>` | 标记 invalid,文件不动 | agent/人 | 写真源+索引 |
| 时序 | `recall --as-of <date>` | 时间点查询(沿 supersede 链) | agent | 同 recall |
| | `recall --deep` | 附带原料证据列表(单独返回,带引用关系) | agent | 同 recall |
| admin | `rebuild` | 删索引后全量重建 | 人/CI | 重写 .index/ |
| | `sleep` | 手动触发睡眠 M(`--reason` 附带推理者) | 人/cron | T0 直改;T1 由推理者裁决并执行;一睡眠一 commit |
| | `proposals` | 列出未裁决提案 | 人 | 无 |
| | `decide <id>` | 环外翻案:接受或否决一条提案 | 人 | 记入账本;接受时写真源 |
| | `inspect` / `gc` / `export` | 体检 / 物理清理 invalid 文件(唯一的删除入口)/ 全量导出 | 人 | export 无副作用 |
| 接入 | `skill` | 打印 agent skill 文本(由提示模块渲染,与执行器纪律同源) | 人/安装脚本 | 无 |
| | `migrate` | 旧布局(四域)升级到 schema 布局 | 人 | 重写真源路径 |
| 安装 | `setup` | agent 读 setup 文档自接线(探测宿主→装钩子→验证) | agent | 写宿主配置 |

- **幂等**:`record` 以 name 为键可重放;`rebuild` 任意次等价。
- **错误模型**:校验失败返回结构化错误(字段+原因),agent 可自修复重试。
- **敏感**:export 全量含 archive,提示用户确认。
