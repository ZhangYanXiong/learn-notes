# MCP 协议：概念、核心能力与实践

**版本：**2026-10-12　｜　**面向：**Agent 学习者与应用研发人员　｜　**规范基准：**MCP `2026-07-28`

> **体系导航：**[学习地图](<../README.md>)｜[Agent Loop](<../基础机制/01-Agent如何运行：Loop.md>)｜[Agent Harness](<01-Agent Harness负责什么.md>)｜[A2A 协议](<03-如何用A2A连接Agent.md>)

## 阅读入口

- **首次阅读：**[1. 它解决什么问题](#1-它解决什么问题) → [2. 三类核心能力如何区分](#2-三类核心能力如何区分) → [3. 一次工具调用的完整路径](#3-一次工具调用的完整路径)。
- **动手与接入：**[7. 最小动手实验](#7-最小动手实验) → [8. 接入真实系统时的设计要点](#8-接入真实系统时的设计要点)。
- **版本差异按需查：**[5. 2026-07-28 版需要记住的变化](#5-2026-07-28-版需要记住的变化)。

## 一页结论

1. **MCP（Model Context Protocol）是 AI 应用连接外部能力的协议。**它约定应用如何发现和调用工具、读取资源、获取提示词模板；不规定模型怎样思考、任务怎样编排。[规范总览](https://modelcontextprotocol.io/specification/2026-07-28)
2. **Host、Client、Server 是三个不同角色。**Host 是面向用户的 AI 应用；它为每个 Server 建立一个 MCP Client；Server 对外提供能力，可以在本机或远端运行。[架构概述](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
3. **Tool、Resource、Prompt 是服务端的三类核心能力。**Tool 执行操作，Resource 提供可读取的内容，Prompt 提供可复用的消息模板。常见交互分别由模型、应用和用户发起，但具体界面由 Host 决定。[服务端能力](https://modelcontextprotocol.io/specification/2026-07-28)
4. **MCP 不是权限系统。**工具能被发现，不代表当前用户获准调用。Host 要控制暴露、确认和结果使用；Server 要校验调用者权限与参数。[安全原则](https://modelcontextprotocol.io/specification/2026-07-28#security-and-trust--safety)
5. **本文以 `2026-07-28` 版为准。**这一版采用无会话、逐请求携带版本和能力元数据的核心协议；旧教程中的 `initialize` / `initialized` 握手和 `Mcp-Session-Id` 属于此前版本。长任务 Tasks 已转为可选扩展。[版本说明](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

## 1. 它解决什么问题

设想一个诊断 Agent 要读取订单接口的指标、查询日志，再生成报告。没有统一协议时，每接一个数据源或工具，都可能要分别设计能力描述、参数格式、调用与返回方式。MCP 提供一套通用的发现和调用约定，让不同 Host 可以接入实现该协议的 Server。

```text
用户 ─→ AI 应用（Host）─→ 模型
              │
              ├─→ MCP Client A ─→ 指标 MCP Server ─→ 指标系统
              └─→ MCP Client B ─→ 日志 MCP Server ─→ 日志系统

Host：组织对话、模型调用、权限和工具结果
Client：与一个 Server 按 MCP 通信
Server：把某个系统的能力以 MCP 形式提供出来
```

**关键边界：**模型可能选择某个 Tool，但实际连接、权限检查、调用和结果进入上下文的方式由 Host 管理。Server 也可以在完全没有模型参与的情况下，被普通程序作为 MCP Client 调用。[架构概述](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)

## 2. 三类核心能力如何区分

| 能力 | 典型作用 | 常见方法 | 诊断案例 |
| --- | --- | --- | --- |
| **Tool** | 查询、计算或执行操作；可能有副作用 | `tools/list`、`tools/call` | `query_latency_metrics(service, range)` |
| **Resource** | 按 URI 读取上下文数据 | `resources/list`、`resources/read` | `schema://orders/api` |
| **Prompt** | 按名称和参数取得消息模板 | `prompts/list`、`prompts/get` | `diagnose_latency(service)` |

区别主要在**交互语义**，不能只按是否“读数据”判断：查询实时指标可以做成 Tool，因为它需要模型选择参数并发起查询；稳定且可按 URI 读取的接口说明适合 Resource。Prompt 生成的是供应用使用的消息，不等于系统级指令，也不会自动取得更高权限。[Tool 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)、[Resource 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)、[Prompt 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)

### Tool 的契约

一个 Tool 至少需要清楚的名称、描述和输入 Schema；还可声明输出 Schema。Client 先用 `tools/list` 发现能力，再用 `tools/call` 提交名称和参数。返回值可包含文本、图片、资源链接或 `structuredContent`。业务执行失败可在工具结果里标记 `isError`；协议层错误则表示请求本身无法正常处理。不要把任一种返回文本直接当作可信指令。[Tool 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

### Resource 与 Prompt 的契约

Resource 以 URI 标识，可以是具体资源，也可以是带参数的 URI 模板。Client 通过 `resources/read` 获取内容；数据是否进入模型上下文仍由 Host 决定。Prompt 是命名的模板，Client 调用 `prompts/get` 时提供参数，Server 返回构造好的消息内容。[Resource 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)、[Prompt 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)

## 3. 一次工具调用的完整路径

```text
Host 的 MCP Client          MCP Server                 模型 / Host
       │                         │                          │
       ├─ server/discover ──────→│ 了解版本和能力（可选）      │
       ├─ tools/list ───────────→│ 返回工具定义               │
       │←─ 工具名称、描述、Schema ┤                          │
       │───────────────────────────────────────→ 注册可用工具 │
       │←─────────────────────────────────────── 选择工具和参数│
       ├─ tools/call ───────────→│ 校验并执行                 │
       │←─ 结果 / 错误 ──────────┤                          │
       │───────────────────────────────────────→ 校验、整理结果│
```

`server/discover` 是 Server 必须实现的能力，但 Client 可以直接发其他请求并处理版本不兼容错误。`2026-07-28` 的每个请求都携带协议版本与 Client 能力等 `_meta` 信息；HTTP 传输还要求 `MCP-Protocol-Version`、`Mcp-Method` 等请求头。下面是便于观察结构的 `tools/call` 请求体，展示字段之间的关系：[架构交互示例](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)、[HTTP 传输规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query_latency_metrics",
    "arguments": {"service": "order-api", "minutes": 30},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": {"name": "study-host", "version": "1.0.0"},
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```

若走 Streamable HTTP，还要按规范发送 `Mcp-Method: tools/call` 和 `Mcp-Name: query_latency_metrics`。实际开发通常交给 SDK 处理报文，不手写这些字段。[HTTP 传输规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)

## 4. 本地与远端怎么通信

| 传输 | 常见位置 | 要点 |
| --- | --- | --- |
| **stdio** | Host 启动本机 Server 子进程 | 标准输入输出承载一行一条 JSON-RPC 消息；日志写 `stderr`，不能污染 `stdout` |
| **Streamable HTTP** | 独立部署的远端 Server | HTTP POST 承载请求；可结合 SSE 传送流式更新；需要处理网络认证与访问控制 |

传输方式决定消息怎么送达，Tool / Resource / Prompt 决定消息表达什么。选用 stdio 或 HTTP 不会改变业务能力本身。旧版 HTTP+SSE 传输已被标记为弃用，阅读旧教程时应核对版本。[stdio 规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)、[Streamable HTTP 规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)、[版本说明](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

## 5. 2026-07-28 版需要记住的变化

| 主题 | 当前理解 | 阅读旧资料时的检查点 |
| --- | --- | --- |
| 协议状态 | 核心请求无会话；请求各自携带版本、能力和相关元数据 | `initialize`、`initialized`、`Mcp-Session-Id` 是旧版流程 |
| 能力发现 | Server 实现 `server/discover`，Client 可按需调用 | 不再把初始化握手当作每次连接的前提 |
| 需要用户补充信息 | 使用多轮请求机制，Server 可返回 `input_required`，Client 补充后重试 | 不假定 Server 必须保持双向长连接 |
| 长任务 | Tasks 是双方显式支持的扩展 | 不把长任务状态管理误认为核心 Tool 的默认能力 |
| 旧能力 | Roots、Sampling、Logging 已弃用，但仍保留兼容窗口 | 新实现先核对替代方案与 SDK 支持 |

这些是**协议版本差异**，不是所有产品或 Server 已同步升级的保证。接入时应核对双方支持的协议版本和 SDK 兼容性。[正式版本公告](https://blog.modelcontextprotocol.io/posts/2026-07-28/)、[规范总览](https://modelcontextprotocol.io/specification/2026-07-28)

## 6. 与 Agent Loop、Harness、A2A 的边界

| 层次 | 回答的问题 | 在诊断案例中的职责 |
| --- | --- | --- |
| **Agent Loop** | 下一步做什么，何时停止？ | 决定先查指标还是先查日志，并评估证据是否充分 |
| **Harness** | 如何控制真实执行？ | 工具白名单、权限、超时、预算、日志与审批 |
| **MCP** | 如何发现并调用外部能力？ | 按统一协议列出、调用指标和日志能力 |
| **A2A** | 如何把任务交给另一个独立 Agent？ | 向远端诊断 Agent 交付目标、跟踪任务和产物 |

一个 MCP Server 可以只是传统服务的适配器，完全不包含 Agent。若对方是有独立目标、状态和任务生命周期的 Agent，再考虑 A2A。MCP 也能被 Agent 内部使用：远端 Agent 接到 A2A 任务后，可以通过 MCP 查询指标。详见本目录的 [Loop](<../基础机制/01-Agent如何运行：Loop.md>)、[Harness](<01-Agent Harness负责什么.md>) 和 [A2A](<03-如何用A2A连接Agent.md>)。

## 7. 最小动手实验

用官方 Python SDK v2 做一个只读 Server，分别暴露 Tool、Resource 和 Prompt。下面代码依据[官方 First steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/) 的 API，目的是识别三种能力的注册方式；它不需要连接真实业务系统。

```python
from mcp.server import MCPServer

mcp = MCPServer("StudyDemo")

@mcp.tool()
def add(a: int, b: int) -> int:
    """计算两个整数的和。"""
    return a + b

@mcp.resource("guide://mcp")
def guide() -> str:
    """返回一小段学习资料。"""
    return "MCP Server 可以提供 Tool、Resource 和 Prompt。"

@mcp.prompt()
def explain(topic: str) -> str:
    """生成一个讲解主题的提示词。"""
    return f"请用一个具体例子解释 {topic}。"
```

环境要求与运行命令以[官方安装说明](https://py.sdk.modelcontextprotocol.io/get-started/installation/)和[调试说明](https://py.sdk.modelcontextprotocol.io/get-started/)为准：Python 3.11+、`uv add "mcp[cli]"`，把代码保存为 `server.py` 后运行 `uv run mcp dev server.py`。在 Inspector 中分别查看 Tool、Resource 和 Prompt；先调用 `add(1, 2)`，再读取 `guide://mcp`，最后给 `explain` 传入 `MCP`。这里的示例仅作为学习材料，未在本知识库中运行。[官方 First steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

完成后，能回答三个问题就抓住了基础：**谁决定使用这个能力？Client 通过哪个方法发现或获取它？Server 返回的数据进入模型前由谁把关？**

## 8. 接入真实系统时的设计要点

- **先划清权限。**Host 控制哪些 Server 和 Tool 对当前用户可见；Server 按调用身份与授权范围再次校验，不能只信任工具描述或模型输出。远端 HTTP Server 的授权机制见[官方规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)。
- **保持工具边界清楚。**名称和描述说明业务意图；输入 Schema 约束参数；有稳定结构的结果声明输出 Schema。写操作应明确副作用，并由应用设置适当确认流程。[Tool 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- **把外部内容当数据。**Resource、Tool 结果和第三方 Server 的描述都可能包含错误或恶意指令；Host 应区分这些内容与自己的可信指令。[安全原则](https://modelcontextprotocol.io/specification/2026-07-28#security-and-trust--safety)
- **按业务事实处理失败。**区分协议错误、参数错误、业务失败和超时；对有副作用的调用考虑重试后的重复执行问题。长任务要明确是否使用 Tasks 扩展，不把普通 Tool 结果当作持久任务状态。[Tool 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)、[Tasks 扩展](https://tasks.extensions.modelcontextprotocol.io/specification/2026-07-28/tasks)

## 官方资料

- [MCP 2026-07-28 规范总览](https://modelcontextprotocol.io/specification/2026-07-28)
- [架构与完整交互示例](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
- [Tool](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) / [Resource](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) / [Prompt](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts) 规范
- [Python SDK 入门](https://py.sdk.modelcontextprotocol.io/get-started/)与[版本迁移](https://py.sdk.modelcontextprotocol.io/migration/)
- [2026-07-28 版本公告](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
