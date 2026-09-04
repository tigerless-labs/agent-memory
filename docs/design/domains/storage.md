# 域:Storage(DS)

1. **Metadata** — 作者:Claude;评审:Ryan;2026-09-01;修订 2026-09-03(schema 驱动的树、两态);状态 **accepted**
2. **Context and Scope** — 真源、投影、原料三个物理组件的结构与边界。
3. **Goals / Non-Goals** — 目标:人类可读可 git、索引即缓存、失效不销毁、树由类型决定而非由 agent 起名。
   不做:目录级摘要与 sidecar、图索引(ADR-004)、字段级补丁合并。

## 4. The Actual Design

```
memory/
├── MEMORY.md            根索引:一行一条,只列 active,预算硬约束(常驻注入的唯一来源)
├── schemas/             记忆类型定义,随库版本化,owner 可改可加(ADR-008)
├── <type>/<group>/<key>.md   叶子即记忆;目录由叶子路径产生,目录本身没有内容
├── archive/             append-only,默认不进检索面
│   ├── sessions/        会话原料:每条消息带序号与时间,是 provenance 指针的坐标系
│   └── provenance/      可选的摘录副本;指针是主形态
├── dream-reports/       每次睡眠一份:动了什么、为什么、证据指针
├── .index/              全部可重建:manifest、现役 FTS、历史 FTS、原料 FTS、access log
└── .state/              不可重建的运行态:蒸馏水位线、待重试写入、写路径锁、钩子日志
```

`.index/` 与 `.state/` 的分界即「可重建」这条线:删 `.index/` 零知识损失;删 `.state/`
只损失「蒸馏到哪了」与「哪些写入待重试」,代价是重复蒸馏,不是丢知识。

**记忆类型 = 一份 schema。**每份只声明四件事:类型名与槽位说明(agent 看到的「出现什么迹象就写一条」)、
键字段(同键同文件,键的 slug 就是文件名与稳定 id)、分组字段(决定子目录)、模式(upsert 或 add_only)。
字段来源在库里全局声明一次:`system`(当前用户、项目、日期,由宿主或库填)、`menu`(从现有目录清单里选,
或明确标记新建)、`field`(agent 自由填)。**目录段只能来自 system 或 menu 字段;field 只能进文件名。**
这是路径不分裂的机制保证。出厂类型:profile(单文件)、preference、entity、event(add_only,按月分组)、
decision / procedure / fact(按项目分组)、experience、reference。

**路径是一条约定,不是模板:`<type>/<group>/<key>.md`。**库渲染路径:键字段 slug 化(小写、连字符、长度上限、
可移植段规则:非法字符与保留名清洗,不可移植的段加哈希后缀)、分组段与现有目录精确匹配、缺目录即建、
深度受 config 硬上限。agent 不写路径;路径从它交回的字段算出。目录承担的功能只有三个,都不需要内容:
scope 前缀过滤、同目录免费邻域、menu 的候选来源。

**单条记忆文件**:frontmatter 携带 name(键 slug)、abstract(一句话检索面)、type、status、created / updated、
valid_from、invalid_at、superseded_by、weight、author、links、provenance,以及 schema 声明的键与分组字段;
正文自由 markdown。

**两态(ADR-009)。**status 只有 active 与 invalid。失效只有两个来源:被后继替换(superseded_by 指向后继,
后继的 valid_from 等于前驱的 invalid_at,同一瞬间)、被删除(invalid_at 有值,superseded_by 为空)。
搬家、改 abstract、追加 links 或 provenance、结算 weight 都不改这四个字段。invalid 文件留在原路径,
默认检索面看不到,历史检索面与 `--as-of` 看得到。物理清理是人在 CLI 上发起的独立命令,Manage 到不了。

**证据 = 指针,只增不减。**provenance 是「会话 + 消息范围」的列表;摘录副本可选。写入路径要求每条记忆
至少一条指针,边界写入缺省填本批增量的范围。update 追加指针,supersede 让后继从自己的指针起步,
前驱的指针原封不动;删除只标记记忆,永远不碰原料。

**文件边界公理:失效原子 = 文件边界**。一个文件装作为整体一起过期的一份知识
(supersede、weight、召回单位都是文件)。同生共死测试:某部分会单独过期 → 拆;
两文件永远同时失效 → 合。粒度由类型的键决定;写时保证「同一件事不会划成两份」,拆合的事后纠正归 M。

**图 = 文件里的四种指针**(ADR-004):关联边 links、时序边 superseded_by、证据边 provenance、
归属边路径本身。无边索引;遍历 = agent 读文件跟指针。

**原料分层**:完整 trace 落在 `sessions/`,每条消息带序号与时间,任何分块都只是索引产物,指针永远指消息。
零丢分两级:指针级无条件,全量级依赖归档开关。

5. **Alternatives Considered** — SQLite 真源 + Vault 投影(ADR-001 否);OpenViking 的路径模板与 L0/L1 sidecar
   (一份模板身兼抽取、结构、路径、合并、向量、目录摘要六职,且目录名由模型自由填导致分裂;记忆目录的 sidecar
   对其自测得分贡献不足百分之一);active / stale / retired 三级阶梯(中间一级从未接上行为,收成两态)。
6. **Cross-cutting** — author 字段支撑多 agent 矛盾裁决;archive 含原文,export 时提示。
7. **Risks** — access log 不可重建(运行遥测,丢了 = M 证据重新积累,非知识损失);
   类型之间的边界只靠槽位说明裁定,重叠处要在出厂说明里写明谁赢;长文档检索面(TODO)。
