# API:MCP 面

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**

MCP 是轻量接入手段(手动或规则提示触发),**不是独立写入策略**——工具调用收敛为
与 CLI 相同的核心调用,同请求同结果(P1 验证项)。工具**少而高层**,
不暴露底层 CRUD(link/boost/patch 等留在 CLI admin)。

| 工具 | 映射 | 说明 |
|---|---|---|
| `memory_recall` | recall | 返回 L0 列表;参数含 scope / as_of / deep |
| `memory_read` | read | 按 name+层级(abstract/outline/full)读取 |
| `memory_record` | record | 写入;schema 强制 frontmatter 必填字段 |
| `memory_correct` | correct | update / supersede |
| `memory_feedback` | (admin) | boost / penalize 显式反馈 |

- 部署:本地进程或 Docker 容器内与 CLI 同体;跨 agent 共享同一盘。
- 超时、错误码与结果结构在实现层与 CLI 共用一套契约对象。
