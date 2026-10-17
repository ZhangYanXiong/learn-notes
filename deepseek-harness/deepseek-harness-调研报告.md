# DeepSeek Harness (dsh) 架构调研报告

> 版本：`0.1.0-rc.5`（Developer Preview，官方声明会有破坏性变更）
> License：MIT ｜ 出品方：DeepSeek AI ｜ 调研日期：2026-08-14
> 代码基线：本地 checkout（master 分支）

---

## 目录

**第一部分　架构调研（主体）**
1. 项目定位与总览
2. 仓库分层与包布局
3. Cordis 框架基础
4. 能力接缝模型（Capability Seam）
5. 核心运行时 spine
6. 事件系统与扩展点
7. 会话与持久化（事件溯源）
8. 工具管道
9. LLM 适配层
10. Agent 作用域与隔离
11. Web GUI 架构（host / client 双半）
12. 部署与组合（Profile / Bundle）
13. 质量工程体系

**第二部分　专题补充（关注点）**
- A. 技术方案
- B. 是否可在现有智能体平台使用
- C. 切入方式
- D. 特色功能

**第三部分　总体评价与建议**

---

# 第一部分　架构调研

## 1. 项目定位与总览

DeepSeek Harness（简称 `dsh`）是 DeepSeek AI 开源的**智能体运行框架 / Agent Harness**，不是一个 SDK 库，而是一个可独立运行、也可被集成的完整 agent 产品底座。

其唯一核心设计原则是 **"一切皆插件"（everything is a plugin）**：模型适配器、工具注册表、会话日志、系统提示词组装、乃至 agent 主循环本身，都是插件。因此每一部分都能从配置中被替换，**不存在需要打补丁的"特权内核"**。底层构建在 DeepSeek 团队 vendor（源码内嵌）进来的 [Cordis](https://github.com/cordiverse/cordis) 插件框架之上，其设计思想见论文《A Programming Paradigm for Spatiotemporal Composability》。

三种典型运行形态：

| 形态 | 命令 | 说明 |
|---|---|---|
| Web 应用 | `npx @deepseek-ai/dsh web` | 本地 Web UI，默认 `127.0.0.1:3080` |
| Headless 一次性任务 | `dsh --profile headless "task"` | 无 server，跑完打印结果退出 |
| 被驱动的后端 | SDK / ACP / JSON-RPC | 嵌入其它系统或被平台驱动 |

## 2. 仓库分层与包布局

Monorepo（pnpm workspace），核心目录：

```
vendor/      内嵌的 Cordis 源码（带上游 SHA 的 manifest）
packages/    @deepseek-ai/dsh-<pkg>，按 group 组织
python/      Python SDK + 打包 runtime
native/      landlock-run（Linux 沙箱启动器，C11）
apps/cli/    dsh CLI 入口
examples/    可运行的 cordis.yml 示例
docs/        架构文档、生成的目录、cookbook
scripts/     仓库门禁与生成器
website/     VitePress 文档站
```

`packages/` 下按 group 划分，每个 npm 包统一命名 `@deepseek-ai/dsh-<name>`。关键 group：

| Group | 职责 | 类别 |
|---|---|---|
| `core/` | 产品 API 主干：session、system-prompt、tools、agent、agent-loop、scope | 稳定 API |
| `llm/` | LLM 能力族：抽象服务 + provider 适配器 | 稳定 API |
| `typert/` | 类型图生成、artifact 加载、运行时 registry | 稳定 API |
| `api/` `host/` `client/` | 远程 BFF、Web-GUI 宿主半、浏览器半 | 稳定 API |
| `shell/` `subprocess/` `terminal/` `fs/` `lsp/` | 执行世界能力族 | 稳定 API |
| `sandbox/` `e2b/` | 进程隔离 / 远程沙箱 | 稳定 / POC |
| `code-runtime/` | 代码执行（Code Mode） | 稳定 API |
| `subagent/` `workflow/` `skill/` `compaction/` | 高阶 agent 能力 | 稳定 API |
| `session/` `session-query/` `storage/` | 持久化数据面 | 稳定 API |
| `sdk/` `acp/` `hooks/` `mcp/` | 对外协议 / 集成桥接 | 稳定 API |
| `interaction/` `plan/` `todo/` `goal/` | 人机协作面 | 稳定 API |
| `extensions/` | agent 运行时自我修改 | 稳定 API |
| `preset/` `bundle/` `boot/` | 组合与启动 | 稳定 API |
| `guard/` `context/` `feedback/` `settings/` `credentials/` | 策略与配置 | 稳定 API |

依赖铁律：**扩展插件只依赖 Service Definition，绝不依赖具体 provider**。例如 `dsh-agent-loop` 是可替换的，UI/hook/tool 插件都依赖 `dsh-agent`（定义）而非 loop（实现），这样主循环本身也能被换掉。

## 3. Cordis 框架基础

Cordis 用五个概念支撑起整个可组合体系：

1. **Plugin = 实现 Service 的对象**：可以是带 `inject` / `apply(ctx)` 字段的函数，或 `Service` 子类，其生命周期由 Cordis 挂载到当前 context。
2. **Context 是服务仓库**：服务占据稳定的 `ctx.<key>`（如 `ctx.tools`、`ctx.llm`、`ctx.sessions`），其它插件**按 key 查找**而非 import 具体实现。可选服务用 `ctx.get(name)` 读全局服务表，声明式注入用 `ctx.<name>`（拓扑敏感）。
3. **依赖通过 `inject` 声明**：一个插件声明所需服务后会等到这些服务存在才加载。**加载顺序由服务需求表达，而非手写启动序列。**
4. **类型化事件**：通过 TypeScript 声明合并（declaration merging）声明事件名与载荷，按四种模式分发：

   | 模式 | 是否 await | 顺序 | 有返回值 |
   |---|---|---|---|
   | `emit` | 否 | 注册顺序观察 | 无 |
   | `waterfall` | 否 | 注册顺序观察 | 有 |
   | `parallel` | 是 | 并行观察 | 无 |
   | `serial` | 是 | 注册顺序观察 | 有 |

   分发模式是事件公开契约的一部分，用 `@mode` JSDoc 标注，生成的目录会校验声明与分发点一致。

5. **注册即可逆副作用（registrations are effects）**：prompt section、tool schema、adapter、provider、listener 全部通过 `ctx.effect()` / `ctx.on()` 安装，reload / teardown 时按序回退。每个注册都返回 disposer。

**Waterfall 语义（关键）**：`ctx.waterfall` 是**环绕式中间件**——listener 收到 `(...args, next)`，调 `next()` 才向下委托（可拿到下游返回值），直接返回则**短路**。协作式 listener 通常改写共享的 request/decision 对象后再委托；策略型 listener 拥有决策权时可直接短路。这是拦截、改写、策略否决的统一机制。

**Loader 配置**：`cordis.yml` 中插件 `config` 与 entry `disabled` 字段允许 `!!js` 表达式（在声明注入激活后对该插件 context 求值），其它元数据保持字面量。环境相关的插件选择用 overlay 表达。

## 4. 能力接缝模型（Capability Seam）

这是 dsh 最核心的架构抽象。一个**能力接缝**是一个可替换能力，由三个角色构成：

- **Service Definition**：定义接口的 Cordis `Service`（抽象类如 `ShellExecutor`，或具体 registry 如 `WebRuntime`；绝不是 TS `interface`），拥有 `ctx.<key>` 与词汇类型。
- **Service Provider**：一个或多个实现。
- **Consumer**：一个或多个使用者，通常是面向模型的工具。

**规范范例 `packages/shell`**：
- `dsh-shell`（Service Definition）
- `dsh-bash-local` / `dsh-bash-sandbox`（Provider）
- `dsh-tool-bash`（Consumer）

角色在独立演进时占据不同包；一个包也可同时拥有多个角色（如 `dsh-llm` 同时是 Definition 和 Consumer）。**接缝是完整能力，绝非单一角色**——加一个能力意味着把三个角色都设计好。

**为什么接缝如此重要**：换一个 provider 就能改变整个产品行为。文件系统和子进程 provider 共享同一"执行世界"，把它们指向远程沙箱（如 E2B），Bash / PTY / LSP 会**一起搬过去，无需 fork provider**。这是 dsh 可组合性的技术根基。

## 5. 核心运行时 spine

`packages/core` 是每个组合都会启动的主干，六个包在一个循环里协作：

| 包 | 拥有 | ctx key |
|---|---|---|
| `session/` | append-only `SessionEvent` 日志与内存 store（唯一真相源） | `ctx.sessions` |
| `system-prompt/` | prompt section 与 tool schema 组装 | `ctx.systemPrompt` |
| `tools/` | 作用域化工具 registry 与守护执行管道 | `ctx.tools` |
| `agent/` | `Agent` 接口、活动 registry、initiator scope、`agent/*` 事件 | `ctx.agents` |
| `agent-loop/` | 实现 `Agent` 契约的具体驱动 | `ctx.agentLoop` |
| `scope/` | 每 agent 作用域注册原语（唯一非 service 的库） | 无 key |

### 5.1 Turn / Step 执行流程

- **turn**：一次输入认领的完整处理，输入被认领前开启，无欠债时关闭。
- **step**：一次模型请求 + 其触发的工具调用；一个 turn 含零或多个 step。

```text
turn/start
  认领 next-step 输入 + 一条排队消息
  组装 prompt sections + tool schemas
  -> agent/pre-step               可改写 / 拒绝消息（拒绝或首次空认领仍关闭一个无 step 的 turn）
     step/start
     追加为 user/message
     从日志派生模型历史 deriveMessages()
     agent/request -> llm/stream -> assistant/chunk* -> assistant/message
     tool/call* -> tools/pre-execute -> tools/execute -> tools/post-execute -> tool/result*
     step/end
     工具还欠一次请求 或 新输入到达 -> 认领 -> 下一 step
  -> agent/turn-stopping
turn/end
```

`turn/*`、`step/*`、`user/message`、`assistant/*`、`tool/*` 是**持久化 session 事件**；`agent/pre-step`、`agent/request`、`llm/stream`、三个 `tools/*` 是 **waterfall 扩展点**；`agent/turn-stopping` 是 serial 无 `next()`。

### 5.2 Agent 句柄与所有权

通过 `ctx.agents.create()`（建新会话）/ `resume()`（载入持久会话）/ `fork()` 创建 agent，返回 `AgentHandle`：`{ agent, dispose() }`。**disposer 是一种 capability**——只有持有者能拆掉这个 agent。`dispose()` 依次停 loop、等退出、注销 agent、从 store 移除 session、最后回退其作用域世界。

`Agent` 句柄的核心方法：
- `send(message, target, wakeup)` — 统一的输入投递（`followup` / `steer` / `inject` 是固定预设别名）。
- `inject(message)` — 排入面向模型的上下文到下一个 pre-step，**不唤醒**驱动（文件变更通知、子目录 AGENTS.md、skill 内容、cron 通知等走这条）。
- `cancel(cause, options)` — 取消活动 turn，`keepInbox` 可保留排队工作。
- `whenIdle()` — 等整个 agent 静止。
- `runMaintenance(task)` — 从真正 idle 相位跑一个非 turn 维护任务。

状态只有 `idle` / `running` 两个可观察值（disposal 会移除 agent 并发 `agent/disposed`，不是第三种状态）。

**Inbox** 是投递词汇：两条有序 pending 列表（`next-turn` / `next-step`），作为 agent 持久投影，所有增删改都记录为 `agent/inbox/spliced` 可持久变更。

## 6. 事件系统与扩展点

事件是扩展点，选对 domain 是大多数改动的第一决策：

- **Session 事件**：追加到日志并经 `session/event` 广播的持久事实。事实必须跨 reload 存活时用它。
- **Agent 事件（`agent/*`）**：携带活动 `Agent`——inbox、step、status、request、validation、continuation。观察或拦截运行中的工作时用它。
- **Capability 事件**：把策略与适配器挂到接缝（`fs/*`、`tools/*`、`telemetry/*`），不 import 主循环。

"新行为去哪"的对照（部分）：

| 目标 | 机制 |
|---|---|
| 加模型 provider | 注册 adapter 到 `ctx.llm` |
| 加面向模型能力 | 注册到 `ctx.tools`，schema 自动进 prompt 组装 |
| 给单会话不同能力集 | 组合 agent preset（service row 需 `isolate` realm） |
| 加 shell 执行 | 注册 `ctx.shell` backend |
| 加持久终端 | 注册 `ctx.terminals` backend + `dsh-tool-terminal` |
| 加人类命令 | 注册到 `ctx.commands`，无需模型 turn |
| 加后台任务 | 注册到 `ctx.jobs`，`job_*` 工具收集 / 停止 |
| 拦截请求/工具/turn | 用对应 `agent/*`、`tools/*` 事件 |
| 加模型可见上下文 | `agent.inject()` |
| fork 活动会话 | `ctx.sessions.fork(source, boundary?, childSessionId?)` |
| 加持久会话状态 | 扩展 `SessionEventMap`，从日志渲染重放 |

## 7. 会话与持久化（事件溯源）

这是 dsh 最见功力的子系统。`Session` 是一个 **append-only 的类型化 `SessionEvent` 日志**——单一真相源。

### 7.1 核心不变量：model-visible ⟺ logged

**LLM 消息历史是从日志派生的，从不单独存储**；replay 就是从相同事件重新派生。`deriveMessages()` 把事件日志投影成模型看到的 `Message[]`。**凡是能到达模型请求的内容，都必须能从日志重建**，且有运行时不变量断言。因此新增一个模型可见输入，就必须新增一个 session 事件（扩展 `SessionEventMap` 并从日志渲染）。

### 7.2 事件词汇（`SessionEventMap`）

可合并扩展（merge-extensible）：插件通过声明合并加自己的事件类型（如 compaction 加 `compaction/*`，hook 桥接加 log-only 的 `hook/invoked` / `hook/result`）。核心事件：

- 结构：`turn/start`、`turn/end`（带 `TurnEndReason`）、`step/start`、`step/end`、`session/end-seed`（seed 边界标记）。
- 消息面（Surface）：`user/message`、`assistant/message`（携带 `usage`）、`tool/result`——这三类是 `SurfaceEventType`，产生 LLM 消息，携带 `surfaceOp` 声明如何进入有序 surface。
- 回放/UI：`assistant/chunk`（token 级原始流）、`tool/call`（原始未解析参数）、`todo/write`、`request/header`、`request/context`。

`SessionEvent<T>` 是对 `type` 的判别联合，`switch (event.type)` 无需 cast 即可收窄 `event.data`。因为 map 可合并扩展，**switch 不能用 `assertNever`**——插件加的变体是合法未知值，需 fall through `default`。事件有 `ignorable?: true` 标记：不认识某 `type` 且无此标记时，读者**必须拒绝重建会话**而非静默丢事件。

### 7.3 Surface 投影与压缩

`SurfaceOp` 有两种：`'append'`（正常尾部追加）和 `{ op: 'replace', start, end }`（用新节点遮蔽 `start..end` 范围的 surface 节点，压缩用它，`sourceEventSeqs` 必须涵盖每个被遮蔽节点）。`deriveMessages()` 沿 surface 有序节点走，被 `replace` 遮蔽的节点从派生中删除——**这就是上下文压缩如何在不破坏日志完整性的前提下缩短模型历史**。

派生投影规则：`user/message`→用户消息；`assistant/message`→助手消息（空内容会被跳过，但仍记录以保留 usage）；`tool/result`→携带 tool-result 块的用户消息；注入上下文→按时间序原样投影。`turn/*`、`step/*` 等结构事件不投影成消息。

### 7.4 fork 与持久化契约

`fork(source, boundary?, childSessionId?)` 从一个稳定的 turn 间位置切分（拒绝在开放 turn 内切分），深拷贝 seed 事件 + 子元数据（`parentSession`、`seedLength`、继承 `cwd`）创建活动子会话。

持久化是独立关注点：`ctx.sessions` 只管内存 store，持久化插件订阅 `session/event`、在 `session/flush` / dispose 时落盘。**耐久契约**：日志无损持久每个事件（含 `assistant/chunk`），`seq` 必须连续；所有 `event.data` 必须 JSON 可序列化（`Session.append` 在源头强制，非法数据当场抛错）。后端可选自己的存储编码（JSONL / SQLite），只要 `load` 返回完全一致的追加事件。

## 8. 工具管道

`ctx.tools` 是作用域化 registry + 守护执行管道。

### 8.1 工具定义与 schema DSL

`ToolDefinition` = 模型可见的 `ToolSchema` + 强制的 `output` 规范声明 + `execute` 函数 + 宿主专属调度元数据 + 可选的最终内容回调与 UI 呈现器。作者用 `defineTool()`，它把参数推断绑到校验、把 `execute`/`render` 绑到 output schema 推断。

统一的 JSON-value schema DSL 支持 `string`/`number`/`integer`/`boolean`/`null`/`array`/`object`/`json`/`oneOf`，类型推断精确到 16 层容器后回退 `JsonValue`。`schemas()` 用显式 allowlist 构造模型可见投影——`execute`/`timeoutMs`/`isConcurrencySafe`/呈现回调**绝不泄漏到模型请求**。

### 8.2 执行管道

`ctx.tools.execute()` 把一次调用跑过：

```
tools/pre-execute（可重排的 allow/deny/ask waterfall）
  → 注册的单调 guard（只能减权，不能授权）
  → tools/execute（环绕式包装：超时/重试/指标）
  → tools/post-execute（检查/替换结果）
  → 定义自有的 finalizeContent
  → tools/result（不可变的权威结果）
```

- **PreToolDecision**：`allow` / `deny` / `ask`（只有审批返回 `allowed-once` 才执行）。参数不可改写（历史、审计、UI、执行必须一致）。
- **ToolGuard**：单调策略，返回值无 allow——`undefined` 保持，返回原因即拒绝，所以 listener 顺序无法把拒绝翻回允许。
- **PostToolDecision**：`accept`（可替换 content 或 value 之一，不可两者）/ `block`（把纠正反馈变成 error 结果）。
- 调度模式 `ToolExecutionMode`：`parallel`（可与兄弟重叠）/ `exclusive`（独占并形成排序屏障），loop 据此形成并行池与独占屏障。

### 8.3 作用域与限制

`ToolRestriction`（`allow` / `deny`）对一个 scope 继承的工具做过滤，多个限制取交集，scope 自有注册豁免。被过滤掉的全局工具在 prompt 中缺席且拒绝执行——与不存在的工具无法区分。作用域工具**遮蔽**同名全局工具（per-agent persona / 工具变体机制）。

### 8.4 UI 呈现意图

工具的呈现意图是设计的一部分，`presentCall`/`presentResult` 返回 `card` 标记的渲染意图（`generic`/`terminal`/`diff`/`search`/`read`/`web`），是 `args` 的纯函数，UI 无关（编辑器卡片、CLI 日志行都能投影）。

## 9. LLM 适配层

`ctx.llm` 是接缝，同时拥有 Service Definition 与 Consumer 角色（抽象服务、内容块词汇、流式 chunk 组装器）。

| 包 | 角色 |
|---|---|
| `llm-deepseek` | 直连 DeepSeek 适配器 |
| `llm-pi-ai` | 多 provider 的 pi-ai 适配器 |
| `token-meter` | 回放感知的 token 计量（独立 consumer，`ctx.tokenMeter`） |
| `llm-retry` | provider 作用域重试（监听 `agent/request-error`） |

Provider adapter 注册路由到 `ctx.llm`；retry 与 token 计量作为独立 consumer 拆分，不污染核心接缝。模型请求的信封（`EpochHeader`：call config + 系统提示 + tool schemas）是被记录的会话状态，所以每个请求都是日志的纯函数。

## 10. Agent 作用域与隔离

`scope` 包是一个无依赖的库原语（非 service），提供让"一次注册"同时表达 **per-agent 可见性** 和 **共享生命周期所有权** 的机制。

- `ScopeKey` 是不透明对象身份（按对象身份比较）；出厂 loop 用活动 `Agent` 对象作为自己的 scope key。
- 贡献（工具、prompt section、变量、restriction、listener）要么**全局**（每个 agent 可见），要么**作用域化**（恰好属于一个 scope key）。两级扁平：作用域注册**不向下继承到子 agent**；子树行为用 lineage 数据表达而非 scope 结构。
- `agent.ctx`（agent-scoped context）：通过它的注册既是 scope-visible 也是 scope-lifetime（一个事实驱动两者），listener 参与该 agent 的 scope 过滤分发。
- **shadowing**：最具体者胜——作用域工具/section/变量替换同名全局孪生，仅对该 scope 生效。这是 per-agent persona 与工具变体的机制。

## 11. Web GUI 架构（host / client 双半）

Web 应用被拆成两个"半"：

- **`packages/host`**（宿主半）：API gateway + HTTP 路由 server。
- **`packages/client`**（浏览器半）：shell、wire、object services、slots、`ui-*` 插件。
- **`packages/api`**：远程 BFF 组装 + Typert RPC gateway。

某些子系统（如 `extensions` 的自我修改）是"双半包"——宿主半和浏览器半成对存在，各自保留独立编译程序。Web Client 用 Conversation Node 定义 + 键控渲染器扩展聊天节点。浏览器信任由 `/api` fence 控制，`--trusted-host` 添加受信主机。

## 12. 部署与组合（Profile / Bundle）

运行态由**有序分层**在启动时组合而成。

- **Profile**：存于 Harness home 的命名组合，列出它叠加的 bundle、装的 out-of-tree 插件、以及用户自己的 `cordis.patch.yml`。`web` 和 `headless` 是出厂模板。
- **Bundle**：Cordis config 行 + 其挂载代码的分发格式。`dsh-base` 是每个 profile 的第一层（模型适配、工具、持久化、沙箱、审批策略、settings、credentials、telemetry）；`dsh-web-app` 加浏览器应用；`dsh-headless` 加无 server 的一次性运行器。

分层顺序（后者胜，逐行替换）：
```
各 bundle（profile 声明顺序）
  → profile 的 cordis.patch.yml
  → home 级 $DSH_HOME/cordis.patch.yml
  → 各 --patch overlay（argv 顺序）
```

patch 按 id 定位行，**替换整个 config 值**（非深合并）或插入新行。查看实际启动树：`dsh --profile web --dump-config`。

插件管理：`dsh plugin --profile <name> add <package-or-git-spec>` 转发给 pnpm，安装后自动把声明了 `dsh.bundle` 的依赖并入分层栈。

默认安全姿态：新会话默认 `workspace-write` 权限预设——bash 和文件写入限制在会话工作区和平台临时根；读、网络、进程可见性不约束。`DSH_TOOLS_MODE` 选 `native`/`code`/`both`。

## 13. 质量工程体系

dsh 的工程规范异常严格，值得单列：

- **语言/运行时**：TypeScript（`strict: true` + `noImplicitAny`，每个残留 `any` 需解释），全 ESM（`"type": "module"`），Node `^22.19 || >=24`。
- **构建**：pnpm workspace（`pnpm@11.7.0`），tsc 产出 lib/types + tsdown 打包 runtime，分 host/client 双 face。
- **测试分层**：vitest 单测；**CI coverage gate 要求 `packages/*/*/src` 单文件 100% 覆盖**；keyless snapshot 回放（校验模型/用户可见输出）；real-API e2e（无 key 自跳过）；产品级组合测试（须通过 Loader 启动真实 `cordis.yml`）。
- **静态门禁**：oxlint、jscpd 跨文件克隆检测、knip（死代码）、publint、workspace 约束、NodeNext consumer 检查。
- **文档门禁**：README/JSDoc 与代码同 PR 更新；`doc-sync` 校验一系列生成目录（config-catalog、tool-catalog、cordis-catalog、module-graph 等）的新鲜度；双语配对校验；export JSDoc 校验；文档预算校验。
- **运行时不变量**：每个包拥有 `./invariant`，检查事件/数据关系，`verify-package-invariants` 强制。
- **Agent Note 制度**：非平凡改动须在同 PR 附 Agent Note（决策记录），已归档 note 冻结不可改。

这套体系意味着代码库质量与可维护性很高，但也意味着**任何贡献的门槛都相当高**。

---

# 第二部分　专题补充

## A. 技术方案（小结）

一句话：**TypeScript + ESM + Cordis 插件系统，以"能力接缝"为核心抽象，会话是事件溯源的 append-only 日志，agent loop 是可替换的默认驱动。**

关键技术选择：
- **可组合性优先**：连主循环、模型适配、会话日志都是插件，从配置替换，无特权内核（详见 §3、§4）。
- **事件溯源**：model-visible ⟺ logged 不变量，模型历史从日志派生，支撑 fork/resume/replay/telemetry/压缩（详见 §7）。
- **能力接缝三角色**：Service Definition / Provider / Consumer，一次 provider 替换改变整个产品（详见 §4）。
- **Typert**：自研类型图生成器，从源码类型生成运行时反射与 schema，支撑 Loader 发现与工具 schema 组装。
- **严格工程门禁**：100% 单文件覆盖、doc-sync、运行时不变量、Agent Note（详见 §13）。

## B. 是否可在现有智能体平台使用

**结论：可以，且被设计成"面向互操作"的角色。** 既能作为独立产品运行，也能作为被驱动后端，还能反向编排别的 agent。

### B.1 支持的协议 / 通道

| 协议 / 通道 | 包 | 用途 | 成熟度 |
|---|---|---|---|
| **ACP**（Agent Client Protocol） | `packages/acp` | 把 dsh agent 暴露给程序化客户端（如支持 ACP 的编辑器）。automation-only | 明确产品化 |
| **JSON-RPC over stdio** | `packages/sdk`（protocol/client/server） | 从另一进程驱动 dsh runtime | 稳定 API |
| **Python SDK** | `python/`（`deepseek-harness-sdk` + 打包 runtime） | 子进程方式驱动，走 newline-delimited JSON-RPC | 高层 turns API + 底层 RPC |
| **Claude Code hooks 桥接** | `hooks/hooks-claude-code` | 指向已有 `hooks.json`，忠实运行外部 shell hook | 桥接层 |
| **Codex hooks 桥接** | `hooks/hooks-codex` | 同上，兼容 Codex hook 方言 | 桥接层 |
| **MCP** | `mcp/mcp-client` | 作为 MCP client，把外部 server 工具注册到 `ctx.tools`（支持自动重连） | 已有，**默认不启用**（server 命令是沙箱外可信代码） |

### B.2 反向能力：把别的平台当子 agent

subagent 家族提供对外部 agent 的编排：`subagent-claude-code`（经官方 Claude Agent SDK 拉起真实 Claude Code 子进程）、`subagent-codex`（真实 Codex app-server）、`subagent-acp`（ACP 出进程子 agent）、`subagent-dsh-sdk`（另一个 dsh 实例）。**即 dsh 可把 Claude Code / Codex 作为下属 agent 调度。**

### B.3 SDK 嵌入边界

SDK 只负责"驱动一个已有 runtime"，调用方需自备 runtime 可执行文件和 `cordis.yml`，**不负责创建/构建/配置开发者项目**。Python SDK 会自动拉起打包 runtime。

## C. 切入方式

按接入深度从浅到深：

1. **零安装试用**：`npx @deepseek-ai/dsh web`。
2. **Headless 一次性运行（最适合集成/CI/脚本）**：`dsh --profile headless "task"`，跑到静止把最后一段 assistant 文本打到 stdout，`completed` 退 0 否则退 1，不起任何 server/端口/浏览器——最干净的编程集成点。
3. **SDK 嵌入**：TS SDK（`sdk/client`）或 Python SDK 以子进程 + stdio JSON-RPC 驱动 runtime，把 dsh 当 agent 引擎嵌进自己后端。
4. **协议对接**：已有 ACP 客户端→用 `acp` server；想让 dsh 调度 Claude Code/Codex→用对应 subagent provider；已有 `hooks.json`→用 hooks 桥接。
5. **Profile + Bundle 组合**：`dsh --profile <name>` + `cordis.patch.yml` / `--patch` 定制插件树（详见 §12）。
6. **写插件深度扩展**：`dsh plugin add <spec>` 安装外部 bundle；自研插件挂到文档化扩展点（详见 §6 对照表）。

先决条件：真实模型调用需 `DEEPSEEK_API_KEY`（可选 `DEEPSEEK_BASE_URL`）；从源码跑需先 `pnpm install && pnpm run build`。

## D. 特色功能

### D.1 运行时自我修改（`packages/extensions`）——最独特
面向模型的工具，让 agent 检视自己正在运行的 cordis 插件树与 service API、**编写并运行模型自己写的动态插件包、再撤回它们**（宿主侧 `node:vm` 沙箱执行，浏览器侧对应半在浏览器求值成 live plugin）。agent 能在运行时观察并改造自身能力。

### D.2 Code Mode（`packages/code-runtime`）——工具调用范式创新
`tools: { mode: code }` 下，不逐个 function-call，而是给模型生成一份"工具 SDK"（用 runtime 语言），模型**写一段程序**一次性编排多个工具调用，在 worker 线程执行，捕获打印与返回值。子调用还能经 `tools/code-dispatch-log` waterfall 改写日志副本。支持 `native`/`code`/`both`。

### D.3 子智能体家族（`packages/subagent`）
多 provider 并存：in-process spawn（全新子 agent）、in-process fork（从父已完成历史派生）、ACP/Codex/Claude Code/dsh-SDK 出进程子 agent。支持**可继续的后台子 agent**、子→父 report 通道、子 agent 消息/列举控制工具。

### D.4 Ralph Loop（`workflow/tool-ralph`）
面向不可变目标的 fresh-agent 工作流——每一 round 是全新子会话，**不继承父/兄会话对话**，靠共享工作区 + 一份有界结构化 handoff（status/summary/evidence/next-steps/blocker）传递跨 round 状态。避免上下文污染的长任务范式。

### D.5 三层安全隔离
- **Landlock（`native/landlock-run`）**：约 300 行 C11、静态链接 musl 的 self-restrict-then-exec 启动器，Linux 上按文件系统 allow-list 约束子进程，ruleset 跨 `execve` 继承（子孙全受限，宿主不受限）。**Fail-closed**：内核无法强制则不运行。per-platform npm 包分发。
- **E2B 远程沙箱（`packages/e2b`，POC）**：把整个"文件系统 + 子进程执行世界"放进 E2B Linux 沙箱，本地 bash/terminal/lsp 无需 fork。
- **进程沙箱策略（`packages/sandbox`）**：per-session 约束策略，bwrap/Landlock/Seatbelt 后端。

### D.6 其它亮点
- **Plan Mode（`plan`）**：把计划模式做成可记录的、每 agent 的协作状态（`plan/mode` fold + step 边界 flush + 审阅退出）。
- **上下文压缩（`compaction`）**：接缝化——token 压力摘要 provider + 无模型的 tool-result 剪枝器 + `/compact` 命令；技术上通过 surface `replace` 遮蔽实现（§7.3）。
- **Skill 系统（`skill`）**：provider-neutral 可复用指令目录 + loader，本地/内嵌/远程 provider 模型契约不变，分层 registry。
- **循环卫生守护（`guard`）**：重复工具调用提醒（作为 logged user message 注入）、按调用超时预算。
- **会话检索（`session-query`）**：逻辑语料、有界读取、lineage、事件关系、语义过滤、SQLite 全文搜索。
- **持久终端（`terminal`）**、**LSP 接缝（`lsp`）**、**goal 目标管理**、**后台 job**、**人类 slash 命令平面**、**telemetry（默认关，可完全 opt-out）**。

---

# 第三部分　总体评价与建议

## 差异化优势
dsh 把**可组合性 / 可替换性贯彻到极致**——不是"框架 + 插件市场"，而是连主循环都是插件、连自身运行时都能被 agent 改造。事件溯源的会话模型让 fork/resume/replay/压缩/telemetry 都从一条日志派生，架构一致性极高。对 ACP / MCP / Claude Code / Codex 的多向桥接使它既能被现有平台驱动，也能反向编排它们。工程质量门禁（100% 覆盖、doc-sync、运行时不变量）在同类开源项目中属顶尖。

## 主要风险
- 仍处 **developer preview**，官方明确会有破坏性变更（`SESSION_FORMAT_VERSION` 保持 `0` 且无兼容承诺；后端拒绝旧格式）。
- 深度定制需理解 **Cordis 这套非主流的插件/事件范式**（context/inject/waterfall/effect/scope），学习曲线偏陡。
- 贡献门槛高（严格门禁 + Agent Note 制度）。
- MCP server、web_fetch 等默认不启用，需自行 patch 开启。

## 集成路线建议
- **轻量集成 / 验证**：从 **headless 模式或 SDK** 入手，成本最低。
- **深度扩展 / 定制产品**：走 **profile + bundle + 自研插件** 路线，前置投入是啃透 Cordis 与能力接缝模型。
- **与现有 agent 平台协同**：优先评估 **ACP**（被驱动）与 **subagent provider**（反向编排）两条通道。
- **需要强隔离执行**：Linux 用 Landlock，需完整远程沙箱评估 E2B（注意其 POC 状态）。
