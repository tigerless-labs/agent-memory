# 全局规则

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;状态 **accepted**

不变量的完整清单在根 CLAUDE.md「Invariants」,本文只补规则的执行面归属:

| 规则 | 执行位置 |
|---|---|
| 文件真源 / 索引即缓存 | 写入管线 + `rebuild` 命令;CI 跑「删索引重建等价性」测试 |
| 单一写路径 | 核心库唯一入口对象;adapter 不得直触存储 |
| 读不改真源 | recall 只写 access log;weight 由 M 批量结算回 frontmatter |
| 原料 append-only | archive 模块只暴露 append;无删除接口(清理属 T2 人工) |
| frontmatter 校验 | 写入管线第一步;非法拒收并回错 |
| 并发 | 管线级 flock 串行化;文件级 last-write-wins;git 兜底 |
| 配置 | 所有阈值(M 触发 N、MEMORY.md 预算、聚簇阈值、weight 步长、
  sessions 归档开关)集中在单一 config;无散落魔数 |
| 库核心零 LLM | 核心依赖清单里不允许出现任何模型/推理客户端(CI 检查) |

**测试类别与通过线** 见 docs/testing.md。
