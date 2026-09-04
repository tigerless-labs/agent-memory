# API:钩子接入契约

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**

钩子挂在两个**通用时刻**上,各宿主用自己的方言实现;钩子脚本只做 capture/触发,
零算法(先例:claude-mem ×5 钩子、obsidian-mind)。

| 通用时刻 | Claude Code 方言 | Codex 方言 | Hermes(无 session) |
|---|---|---|---|
| 停顿点(任务收尾,带宽空闲) | SessionEnd / Stop | lifecycle stop 事件 | idle 检测 / cron |
| 淘汰点(context 将被丢弃) | PreCompact | 对应压缩事件 | eviction 回调(如有) |
| 注入点(session 起点) | SessionStart | 对应启动事件 | provider 常驻注入 |

- 钩子失灵不影响正确性:水位线 + 阈值触发 + 闲置扫描兜底(domains/write.md)。
- 钩子只做两件事:把增量交给库(捕获),触发库侧执行器蒸馏。宿主模型不参与写入。
- 异常钩子不得破坏宿主主流程:超时静默退出,错误只进自身日志。
- 安装由 `setup` 完成:探测宿主 → 写入对应钩子配置 → 冒烟验证。
