# dsh vs Hermes Agent 横向对比

> dsh 基线：`0.1.0-rc.5`（Developer Preview）｜Hermes：NousResearch/hermes-agent（MIT）
> 对比日期：2026-08-14 ｜ 关联文档：`deepseek-harness-调研报告.md`
>
> ⚠️ **数据来源说明**：dsh 列源自本地 checkout 直读，可采信；Hermes 列源自官方站点与第三方技术博客（Stars 数、版本号、发布日期在不同来源有出入，如"2025-07 创建" vs "2026-02 发布"），**以 github.com/NousResearch/hermes-agent 官方仓库为准**。

---

## 零、一句话定性

- **dsh**：TypeScript 写的**可组合智能体运行框架 / harness**——"一切皆插件"，连主循环都可替换，强在**架构可组合性、事件溯源、多向互操作、工程门禁**。定位是**可嵌入的引擎底座**。
- **Hermes Agent**：Python 写的**自我进化型智能体**——"越用越聪明"，强在**分层记忆 + 自建技能的学习闭环、20+ 消息平台接入、开箱即用**。定位是**自托管的"数字员工"**。

**核心结论：两者同为开源智能体，但不是严格同类**——dsh 是"给你搭产品的框架"，Hermes 是"直接能用的成品 agent"。选型取决于你要"造引擎"还是"用助手"。

---

## 一、总览速查表

| 维度 | DeepSeek Harness (dsh) | Hermes Agent |
|---|---|---|
| 出品方 / License | DeepSeek AI ／ MIT | Nous Research ／ MIT |
| 本质定位 | 可组合的 Agent **Harness / 框架**（可嵌入亦可独立跑） | 自托管的**自我进化型 agent**（"数字员工"） |
| 主语言 / 运行时 | TypeScript（strict）＋ 全 ESM ＋ Node ^22.19 \|\| >=24 | **Python 3.11+**（uv 包管理） |
| 底层框架 | vendored **Cordis** 插件框架 | 模块化 Python 架构（无插件框架内核） |
| 核心卖点 | 可组合性 / 无特权内核 / 事件溯源 | **分层记忆 + 自建技能学习闭环** |
| 成熟度 / 人气 | Developer Preview（`0.1.0-rc.5`），声明会破坏性变更 | 已大规模采用（GitHub 数万至十余万 Stars） |
| 接入门槛 | 高（需啃 Cordis 范式 + 严格门禁） | 低（单条 curl 一键安装即用） |

---

## 二、逐维度对比

### 1. 定位与形态

| | dsh | Hermes |
|---|---|---|
| 产品形态 | Web 应用 / Headless 一次性任务 / 被驱动后端三形态 | 长驻的自托管 agent + **消息网关进程**，接 20+ 聊天平台 + CLI |
| 是库还是产品 | **框架底座**，可嵌入、可独立跑、可反向编排别的 agent | **成品 agent**，装完即用，面向个人/团队日常自动化 |
| 典型启动 | `npx @deepseek-ai/dsh web`；`dsh --profile headless "task"` | 单条 `curl` 一键安装；跑成 gateway 进程 |
| 部署 | 本地 / 嵌入其它后端 | $5 VPS / GPU 集群 / Serverless（Daytona·Modal），数据留本地 |

### 2. 核心抽象与可组合性

| | dsh | Hermes |
|---|---|---|
| 核心抽象 | Cordis：Plugin=实现 Service 的对象，Context 为服务仓库（`ctx.<key>`） | 模块化 Python（`toolsets.py` / `model_tools.py` 等），非插件框架 |
| 有无特权内核 | **无**——主循环 / 模型适配 / 会话日志全是可替换插件 | 有固定主体（记忆循环、技能循环是内建机制，非可替换插件） |
| 组合 / 定制方式 | Profile + Bundle 分层 + `cordis.patch.yml` / `--patch` overlay | 配置 + 增删工具 + MCP + 自定义技能 |
| 可替换粒度 | 极细（连 agent loop 都能换） | 较粗（在成品框架内扩展工具/技能） |

### 3. 会话 / 状态 / 记忆模型（差异最大处）

| | dsh | Hermes |
|---|---|---|
| 状态范式 | **事件溯源**：append-only 类型化 `SessionEvent` 日志为单一真相源 | **分层记忆**：按访问频率分层（类比 CPU 缓存/内存/磁盘） |
| 具体结构 | 模型历史从日志 `deriveMessages()` 派生；model-visible ⟺ logged | L1 `MEMORY.md`(~800t) + L2 `USER.md`(~500t) 冻结快照注入 system prompt；L3 SQLite FTS5 按需检索；L4 Skills |
| 跨会话持续 | fork / resume / replay 全从同一日志派生 | 跨会话持久记忆，持续完善用户认知模型 |
| 上下文控制 | surface `replace` 遮蔽压缩，不破坏日志完整性 | FTS5 按需检索代替全量塞入 context，抑制 token 线性增长 |
| 设计取向 | **可重放/可审计的严谨真相源** | **越用越懂你的长期记忆** |

#### 3.1 dsh 的"记忆"能力拆解

dsh **没有内建"自我进化的长期记忆"**，但具备构成记忆的基础设施：

| 能力 | 包 | 对应 Hermes 的层 |
|---|---|---|
| 会话持久化（重启 resume 重放） | `session-persistence`（JSONL/SQLite） | 会话内完整历史 |
| 跨会话检索（SQLite 全文搜索 + lineage + 事件关系） | `session-query` / `session-query-sqlite` | ≈ L3（FTS5 按需检索） |
| 跨会话快照引用（注入别的会话有界快照） | `session-reference` | 部分对应"回忆其它会话" |
| 工作区指令注入（`$DSH_HOME/AGENTS.md` + 项目 `AGENTS.md`/`CLAUDE.md`） | `agent-instructions` | ≈ L1/L2（快照注入 system prompt） |
| 技能目录（provider-neutral 指令 + 分层 registry） | `skill` | ≈ L4（Skills） |

**关键差别**：dsh 这些文件/技能是**人写的、静态的**（agent 只读不自写）；Hermes 的 MEMORY.md/USER.md/Skills 是 **agent 自动写、自动进化的**。

#### 3.2 记忆的触发逻辑对比

| 触发环节 | dsh | Hermes |
|---|---|---|
| **指令/记忆注入** | 每个 live session 第一个 `agent/pre-step` 组装 AGENTS.md 基线，折进 step 1 batch | 对话开始时 MEMORY.md/USER.md 冻结快照注入 system prompt |
| **刷新机制** | **触碰驱动、无 file watcher**：仅在成功的 first-party `read`/`write`/`edit` 的 `tools/result` 后检查新 scope，队列 add/replace/remove；跟随结构化 fs 工具而非 shell `cd` | 【公开资料未详述刷新触发】 |
| **去重/抑制** | 同 path + SHA-1 digest 未变不重注入；provider 版本 + 可见状态匹配则跳过读取 | 【未详述】 |
| **检索触发** | 模型**主动调用** `tool-session-query`（按需拉取，非自动注入） | **按需** FTS5 检索（如"上周讨论的 X"） |
| **持久化触发** | `session/event` 广播 + `session/flush`/dispose 时 write-behind 落盘 | 【未详述】 |
| **记忆/技能写入** | **无自动写入**——AGENTS.md 由人写，skill 由外部提供，"记什么"需人或上层插件决定 | **agent 自主触发**：完成难题后自动提炼 Skill、跨会话自动更新用户认知 |

**一句话**：dsh 给的是"**何时加载/刷新/检索**"的机制（触发点明确、可审计），Hermes 给的是"**何时自动学习**"的机制（任务完成即触发自我进化）。dsh 凭 `session-query` + `inject()` + `extensions` 可在其上搭出自动记忆，但官方未内建。

### 4. 工具管道

| | dsh | Hermes |
|---|---|---|
| 工具数量/内置 | 能力接缝按需组合（bash/fs/terminal/lsp/web…） | **40+ 内置工具**（文件、浏览器自动化、MCP、14+ 平台接入等） |
| 定义方式 | `defineTool()` + 统一 JSON-value schema DSL，schema 自动进 prompt | 集中管理于 `toolsets.py` / `model_tools.py`，模块化 |
| 执行管道 | pre-execute→guard→execute→post-execute→finalize→result（审批/守护完备） | 【公开资料未详述审批/守护管道】 |
| 调用范式 | 支持 **Code Mode**（模型写程序一次编排多工具，native/code/both） | 常规逐工具调用 + 浏览器自动化 |

### 5. 扩展与学习机制

| | dsh | Hermes |
|---|---|---|
| 扩展点 | 类型化事件 4 模式（emit/waterfall/parallel/serial）+ 能力接缝三角色 | 增删工具、MCP、自建技能 |
| 技能系统 | `skill` 包：provider-neutral 指令目录 + 分层 registry | **自我进化闭环**：完成难题→自动提炼可复用 Skill→复用中改进（兼容 agentskills.io） |
| 运行时自我修改 | `extensions`：agent 写并运行自己的动态插件再撤回（node:vm 沙箱） | 通过"自建技能"实现能力增长，非运行时改插件树 |
| 取向 | **架构自省与自我改造** | **经验沉淀与自我提升** |

### 6. 互操作 / 平台可用性

| | dsh | Hermes |
|---|---|---|
| 被驱动协议 | ACP、JSON-RPC over stdio、Python SDK | 主要通过消息平台与 CLI 直接使用 |
| 消息渠道 | （无内建 IM 网关） | **20+ 平台**：Telegram·Discord·Slack·WhatsApp·Signal·飞书·钉钉·CLI 等，单网关统一 |
| MCP | MCP client（默认不启用） | MCP 集成（内建） |
| 模型无关 | 通过 adapter（llm-deepseek / llm-pi-ai 多 provider） | OpenAI·Anthropic·OpenRouter（200–300+ 模型）自由切换 |
| 反向编排 | **可把 Claude Code / Codex / 另一 dsh 当下属 agent 调度** | Agent Swarm 子代理并行（见下） |

### 7. 安全隔离

| | dsh | Hermes |
|---|---|---|
| OS 级隔离 | **Landlock**（native C11，Linux 文件系统 allow-list，fail-closed） | 【公开资料未强调 OS 级沙箱】 |
| 远程沙箱 | E2B（POC，整个执行世界搬进远程 Linux 沙箱） | 强调"数据留本地"的隐私姿态；隔离子代理非安全边界 |
| 进程沙箱 | bwrap / Landlock / Seatbelt，per-session 策略 | 【未详述】 |
| 默认姿态 | 新会话 `workspace-write`，写入限制在工作区与临时根 | 本地运行，无遥测 |

### 8. 多智能体

| | dsh | Hermes |
|---|---|---|
| 子智能体 | subagent 家族：in-process spawn/fork、出进程 ACP·Codex·Claude Code·dsh-SDK | **Agent Swarm**：创建隔离子代理处理并行工作流 |
| 工作流 | Ralph Loop（fresh-agent、不继承对话、有界 handoff 传状态） | cron 定时任务调度 |
| fork 语义 | 从稳定 turn 间位置切分，深拷贝 seed + 子元数据 | 【未详述】 |

### 9. 工程质量

| | dsh | Hermes |
|---|---|---|
| 覆盖率门禁 | CI 要求 `packages/*/*/src` **单文件 100% 覆盖** | 【公开资料未披露同等门禁】 |
| 文档门禁 | doc-sync + 双语配对 + JSDoc + 生成目录新鲜度 | 【未披露】 |
| 运行时不变量 | 每包 `./invariant`，`verify-package-invariants` 强制 | 【未披露】 |
| 决策记录 | Agent Note 制度（非平凡改动须附，归档冻结） | 【未披露】 |
| 取向 | **顶尖工程门禁，贡献门槛高** | **模块化、易上手，社区驱动** |

### 10. 成熟度与接入门槛

| | dsh | Hermes |
|---|---|---|
| 发布状态 | Developer Preview，无兼容承诺（`SESSION_FORMAT_VERSION=0`） | 已大规模采用（数万至十余万 Stars） |
| 学习曲线 | 陡（Cordis 的 context/inject/waterfall/effect/scope） | 平缓（Python + 一键安装） |
| 最轻接入点 | Headless 模式（无 server，stdout 取结果，退出码判成败） | curl 一键装完直接对话 |
| 独特高级用途 | 反向编排 Claude Code/Codex；运行时自我修改 | **生成训练数据 / RL 实验 / 导出 tool-calling 轨迹**做微调 |

---

## 三、差异化结论

### dsh 的相对优势
1. **架构可组合性**：无特权内核，连主循环都可替换，适合作为底座深度定制产品。
2. **事件溯源会话**：model-visible ⟺ logged，fork/resume/replay/压缩/telemetry 全从一条日志派生，可审计、可重放。
3. **多向互操作 + 反向编排**：ACP/JSON-RPC/SDK/hooks 被驱动，且能把 Claude Code/Codex 当下属 agent。
4. **强安全隔离**：Landlock（C11 fail-closed）+ E2B + 多后端进程沙箱。
5. **顶尖工程门禁**：100% 单文件覆盖、doc-sync、运行时不变量、Agent Note。

### Hermes 的相对优势
1. **开箱即用**：单条 curl 装完即用，Python 生态，门槛极低。
2. **自我进化闭环**：分层记忆（MEMORY.md/USER.md/FTS5/Skills）+ 自建技能，"越用越聪明"。
3. **消息平台覆盖广**：20+ IM 渠道单网关统一，天然适合做团队/个人"数字员工"。
4. **社区与采用度**：Stars 量级远超 dsh，生态活跃。
5. **训练数据/RL 用途**：可并行生成 tool-calling 轨迹，服务微调与 RL 实验。

### 选型建议

| 你的目标 | 推荐 |
|---|---|
| 造自己的 agent 产品 / 需要深度定制、可替换主循环 | **dsh** |
| 需要强 OS 级隔离执行、可审计的会话真相源 | **dsh** |
| 想被现有平台驱动或反向编排 Claude Code/Codex | **dsh** |
| 想要开箱即用、跨聊天平台的长期记忆"数字员工" | **Hermes** |
| 重视自我学习/技能沉淀、低运维、Python 栈 | **Hermes** |
| 生成微调训练数据 / 跑 RL 轨迹 | **Hermes** |

---

## 四、共同点（都具备）

- MIT 开源、模型无关（dsh 经 adapter，Hermes 经多 provider）
- 支持 MCP、支持子智能体并行、支持技能系统、支持定时/计划机制
- 都强调本地/自托管与隐私（dsh telemetry 默认关，Hermes 数据留本地）

---

## 参考来源

- [Hermes Agent 官方站](https://hermes-agent.org/)
- [About Hermes Agent — Nous Research](https://hermes-agent.org/about/)
- [NousResearch/Hermes-Agent 深度技术解析 - 掘金](https://juejin.cn/post/7639583242592829490)
- [从 Hermes 架构提炼的 Self-Improving Agent 模式 - 掘金](https://juejin.cn/post/7647083669481979930)
- [Hermes Agent 部署 - 华为云](https://www.huaweicloud.com/solution/implementations/deploying-hermes-agent.html)
- dsh：本地 checkout（master）与 `deepseek-harness-调研报告.md`
