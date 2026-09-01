# ADR-007: 实现语言 — Python 3.12 + uv(v0.1)

**Status**: **proposed**(待 Ryan 签字)

**Context**: 简单性验收要求「安装 ≤2 步、依赖 0(除单可执行物)」。候选:
Rust(单二进制最优,MemCLI/实习生方案取向,开发慢)vs Python(实验速度最快,
三套 benchmark 与三宿主驱动全是 Python 生态,SQLite/FTS5 标准库直达,单可执行物
可后期用 PyInstaller/shiv 补)。

**Decision(拟)**: v0.1 用 Python 3.12 + uv 管理;核心库 + CLI + MCP server +
回放驱动器同一 workspace。`uvx agent-memory` 满足安装两步;编译型单二进制留给
v0.2 按需(核心与语言无关,Contract 稳定后可移植)。

**Consequences**: 好——P1–P3 实验周期最短;benchmark 适配零摩擦;招人/协作面最大。
坏——冷启动毫秒级劣于二进制;daemon-free 设计下每次 CLI 调用有解释器开销
(千条规模可接受,压测验证)。
