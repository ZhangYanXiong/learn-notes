# A2A 协议：概念、任务生命周期与 Agent Graph 接入

**版本：**2026-10-12　｜　**面向：**希望理解远端 Agent 通信的学习者与 Agent 应用研发人员　｜　**规范基准：**A2A v1.0.1

> **体系导航：**[学习地图](<../README.md>)｜[Agent Graph](<../编排与协作/01-什么时候需要Agent Graph.md>)｜[Agent Graph Engineering](<../编排与协作/02-如何实现Agent Graph.md>)

## 阅读入口

- **首次阅读：**[1. A2A 解决什么问题](#1-a2a-解决什么问题) → [2. 六个核心概念](#2-六个核心概念) → [3. 一次任务如何流转](#3-一次任务如何流转)。
- **组装案例：**[5.1 完整示例：Graph 委托远端 Agent 诊断延迟](#51-完整示例graph-委托远端-agent-诊断延迟)。
- **深入协议与取舍：**[6. A2A、MCP、API 与任务队列的关系](#6-a2amcpapi-与任务队列的关系) → [7. 落地时的可靠性与安全边界](#7-落地时的可靠性与安全边界) → [8. 最小动手练习](#8-最小动手练习)。

## 一页结论

1. **A2A（Agent2Agent）定义独立 Agent 之间的任务通信方式。**调用方发现远端 Agent 的能力，发送消息，跟踪任务，接收状态和产物；远端 Agent 可以保留自己的模型、工具和内部状态。
2. **核心对象是 Agent Card、Message、Task 和 Artifact。**Agent Card 描述能力与连接方式；Message 承载交互；Task 承载可跟踪的工作；Artifact 承载交付结果。
3. **A2A 适合跨进程、跨团队或跨框架的 Agent 协作。**它定义双方如何交互，但业务流程如何编排、是否批准动作、结果是否可信，仍由应用负责。
4. **长任务应使用 Task。**Task 可以暂停等待输入或授权，调用方可轮询、订阅流或接收推送通知，然后继续同一任务。
5. **A2A 与 MCP、任务队列处在不同层。**MCP 主要连接 Agent 与工具、资源；任务队列负责可靠分发工作；A2A 规定远端 Agent 对外的交互语义。
6. **模型选择 Agent 是应用中的可选路由步骤。**应用先发现并筛选 Agent Card，把合格候选的能力摘要交给模型；程序复核模型的选择，再发起 A2A 调用。固定节点可直接由程序指定 Agent。

## 1. A2A 解决什么问题

设想一个 Agent Graph 要请另一个团队的诊断 Agent 分析订单接口延迟。两者可能使用不同框架、运行在不同服务中，且各自拥有内部工具和会话。调用方需要知道对方能处理什么、如何提交工作、怎样追踪进度、何时补充信息以及从哪里取得结果。A2A 为这些交互提供统一契约。[官方概述](https://a2a-protocol.org/latest/topics/what-is-a2a/)

```text
Agent Graph / 调用方             远端 Agent
        │                           │
        ├── 读取 Agent Card ────────→│ 发现能力、接口和认证要求
        ├── 发送 Message ───────────→│ 提交目标和必要上下文
        │←────────────── Task ──────┤ 获得 taskId 和状态
        │←──── 状态 / Artifact ──────┤ 跟踪进度、取得结果
        └── 校验结果并推进 Graph     │
```

这里的“Agent”指能够在一定目标和权限范围内自主完成工作的服务。一个只执行固定函数、一次请求就返回确定结果的远端服务，通常直接作为 API 或工具接入即可。A2A 的价值主要出现在任务需要持续状态、多轮交互、异步进度或跨系统互操作时。

## 2. 六个核心概念

| 概念 | 作用 | 在诊断案例中的样子 |
| --- | --- | --- |
| **A2A Client** | 发起调用的应用或 Agent | Agent Graph 中的远端诊断节点 |
| **A2A Server** | 对外暴露 A2A 接口的远端 Agent | 诊断 Agent 服务 |
| **Agent Card** | 描述身份、技能、接口、能力和认证要求 | 声明可做延迟诊断，支持流式更新 |
| **Message** | 一轮交互，包含角色和内容片段 | “分析最近一小时订单接口延迟” |
| **Task** | 有 ID、状态和生命周期的工作单元 | 一次延迟诊断任务 |
| **Artifact** | Task 产出的实际交付物 | 带证据引用的诊断结论 |

**Part** 是 Message 和 Artifact 的内容单元，可以承载文本、文件引用或结构化数据。**`contextId`** 用于关联一组相关的消息与任务；**`taskId`** 标识其中某一项具体工作。一个上下文可以关联多个任务，不能把两个 ID 当成同一层的会话编号。[核心概念](https://a2a-protocol.org/latest/topics/key-concepts/)、[Task 数据模型](https://a2a-protocol.org/v1.0.1/specification/)

### Agent Card 是能力说明，不是权限凭证

Agent Card 通常可从 `/.well-known/agent-card.json` 获取，也可以通过目录或预配置地址发现。它提供技能、支持的接口、协议版本和认证要求。调用方据此选择远端 Agent；具体请求仍需要按服务声明的方式认证，服务端也要按自身策略授权。[Agent 发现](https://a2a-protocol.org/latest/topics/agent-discovery/)、[认证规范](https://a2a-protocol.org/v1.0.1/specification/)

### Message 与 Artifact 分别承担什么

Message 用来发任务、补充上下文、请求澄清或说明状态。Task 的最终交付结果应放在 Artifact 中，便于调用方识别并处理。流断开后，临时状态消息可能丢失；重要业务信息应通过可查询的 Task 状态或持久产物核对。[消息与产物规范](https://a2a-protocol.org/v1.0.1/specification/)

## 3. 一次任务如何流转

以“只读诊断订单接口延迟”为例：

1. Graph 读取诊断 Agent 的 Agent Card，确认它支持诊断任务，并取得接口与认证方式。
2. Graph 发送 Message，写明目标、时间范围、只读约束和期望交付物。
3. 远端 Agent 可以直接返回一条 Message；如果需要持续执行，则创建 Task，返回服务端生成的 `taskId`。
4. Graph 根据 Task 状态等待、轮询或订阅进度。诊断 Agent 如需用户明确时间范围，可将 Task 置为 `TASK_STATE_INPUT_REQUIRED`；调用方使用同一 `taskId` 补充回答。
5. Task 完成后，Graph 获取 Artifact，校验证据和结果格式，再决定是否推进后续节点。

```text
SUBMITTED → WORKING → COMPLETED
                 ├─→ INPUT_REQUIRED → WORKING
                 ├─→ AUTH_REQUIRED  → WORKING
                 ├─→ FAILED
                 ├─→ CANCELED
                 └─→ REJECTED
```

`COMPLETED`、`FAILED`、`CANCELED` 和 `REJECTED` 是终止状态；`INPUT_REQUIRED` 与 `AUTH_REQUIRED` 是等待继续的中断状态。已终止的 Task 不能继续接收消息；后续相关工作可在同一 `contextId` 下创建新任务。[Task 生命周期](https://a2a-protocol.org/latest/topics/life-of-a-task/)、[状态定义](https://a2a-protocol.org/v1.0.1/specification/)

`AUTH_REQUIRED` 表示任务执行过程中还需要授权，例如获取访问下游系统的许可；调用 A2A 接口时的身份认证由传输层处理。两者可能发生在同一次工作中，但处理位置不同。[认证与任务授权](https://a2a-protocol.org/v1.0.1/specification/)

## 4. 接口与进度通知

| 操作 | 作用 |
| --- | --- |
| `SendMessage` | 发起交互或继续已有 Task；可返回 Message 或 Task |
| `SendStreamingMessage` | 发送消息并接收实时状态、产物更新 |
| `GetTask` / `ListTasks` | 查询任务状态或列表 |
| `SubscribeToTask` | 对已有且未终止的 Task 订阅更新 |
| `CancelTask` | 请求取消仍在运行的 Task；取消可能因任务阶段而失败 |

当前规范提供 **JSON-RPC、gRPC、HTTP+JSON** 三种标准接口形式。HTTP 形式的流式更新使用 **SSE**；长任务还可以通过 **Webhook 推送**状态更新。调用方也可以使用 `GetTask` 轮询。创建长任务时，若希望提交后立即返回，可设置 `returnImmediately: true`；规范中的普通 `SendMessage` 默认会等待任务进入终止或中断状态。[协议接口与绑定](https://a2a-protocol.org/v1.0.1/specification/)

| 更新方式 | 适合情况 | 需要留意 |
| --- | --- | --- |
| 轮询 `GetTask` | 更新不频繁、实现简单 | 控制查询间隔和总超时 |
| SSE 流 / 订阅 | 需要持续展示进度 | 处理断线重连，并重新查询最终状态 |
| Webhook 推送 | 长任务、调用方不保持连接 | 验证来源、处理重复投递，按 `taskId` 核对状态 |

## 5. A2A 接入 Agent Graph 时如何分工

在 Graph 中，A2A Client 可以作为一个节点的适配层。Graph 给远端 Agent 分配边界明确的 Subgoal；远端 Agent 负责局部探索并返回结果或信息请求。Graph 保存全局 State、判断节点依赖、控制权限与审批，并校验远端输出。[本地 Graph Engineering 笔记](<../编排与协作/02-如何实现Agent Graph.md#63-worker-agent-缺少信息时局部探索与全局协调>)

建议为每次调用保存下面的映射，便于恢复和追踪：

```text
graph_run_id + node_id
    → 远端 Agent 标识 + contextId + taskId
    → 本地节点状态、超时期限和结果引用
```

`graph_run_id` 与 `node_id` 属于本地编排系统；`contextId` 与 `taskId` 属于远端 A2A 交互。用户补充 Worker 当前任务的信息时，应用应把回答送回原 Task；如果请求会改变全局 Goal、权限或其他节点依赖，则先由 Graph 处理。[本地多 Session 路由设计](<../编排与协作/02-如何实现Agent Graph.md#64-统一对话框下的多-session-与-worker-human-in-the-loop>)

### 5.1 完整示例：Graph 委托远端 Agent 诊断延迟

用户请求“只读分析订单接口为什么慢”。Graph 的 `diagnose_latency` 节点已经指定远端诊断 Agent，因此这里由程序直接选择；诊断 Agent 发现缺少时间范围后追问，收到回答后读取指标与日志，最后交付结构化诊断报告。下面是语言无关的 Python 风格伪代码：`SendMessage`、`GetTask` 和 `CancelTask` 表示 A2A 操作；`graph_store`、`interaction_store`、`enqueue` 等表示应用自己的实现，并非 A2A 标准 API。

```python
# Graph 一侧：节点每次被唤醒只推进一步，等待期间不占用执行进程。
def diagnose_latency_node(state):
    key = (state.graph_run_id, "diagnose_latency")
    remote = graph_store.get_remote_task(key)

    if remote is None:
        agent_id = "diagnosis-agent"  # 应用 Registry 中的标识
        card = discover_agent_card(agent_id)
        require_skill(card, "diagnose_api_latency")
        interface = choose_interface(card, "HTTP+JSON")
        credential = obtain_credential(card, state.requester)

        # clientRequestId 是双方约定的幂等字段，不属于 A2A 核心字段。
        request_id = stable_request_id(key, state.plan_version)
        response = a2a.SendMessage(
            interface=interface,
            credential=credential,
            message=Message(
                messageId=request_id,
                role=ROLE_USER,
                parts=[DataPart({
                    "service": "order-api",
                    "time_range": state.time_range,  # 可能为空
                    "goal": "找出延迟升高的最可能原因",
                    "constraints": ["read_only"],
                })],
            ),
            configuration={"returnImmediately": True},
            metadata={"clientRequestId": request_id},
        )
        require_task(response)  # 本节点约定使用 Task；直接 Message 属于契约不匹配
        remote = save_mapping_atomically(
            key, agent_id, card_revision(card), interface,
            response.task.contextId, response.task.id, request_id
        )

    credential = credential_for(remote.interface, state.requester)
    if deadline_exceeded(remote):
        try:
            a2a.CancelTask(remote.interface, remote.task_id, credential=credential)
        except TaskNotCancelable:
            pass  # 任务可能已完成，仍须查询最终状态
        latest = a2a.GetTask(remote.interface, remote.task_id,
                             credential=credential)
        return reconcile_timeout(latest)  # 取消请求不等于已取消

    task = a2a.GetTask(remote.interface, remote.task_id, credential=credential)
    status = task.status.state
    if status in {TASK_STATE_SUBMITTED, TASK_STATE_WORKING}:
        schedule_node_wakeup(key, after="短暂间隔")
        return WAITING_REMOTE
    if status == TASK_STATE_INPUT_REQUIRED:
        question = read_question(task.status.message)
        interaction_store.create_once(
            owner_graph_run=state.graph_run_id,
            owner_node="diagnose_latency",
            remote_task_id=remote.task_id,
            question=question,
        )
        return WAITING_FOR_HUMAN  # 对话控制器向用户展示问题
    if status == TASK_STATE_AUTH_REQUIRED:
        request_authorization_once_out_of_band(state.requester, remote.task_id)
        return WAITING_FOR_AUTH  # 授权完成后再次唤醒节点并 GetTask
    if status == TASK_STATE_COMPLETED:
        report = validate_diagnosis_artifact(task.artifacts)
        graph_store.commit_node_result_once(key, report)
        return {"diagnosis": report, "next": "summarize"}
    if status in {TASK_STATE_FAILED, TASK_STATE_REJECTED, TASK_STATE_CANCELED}:
        return route_remote_failure(task.status, state.retry_policy)
    raise UnexpectedTaskState(status)


# 用户回答进入对话控制器；用 interaction_id 找到原 Task。
def on_user_reply(interaction_id, answer, requester):
    # 先持久化回答与固定消息 ID；网络失败后可重试投递同一回答。
    pending = interaction_store.prepare_reply_once(
        interaction_id, requester, validate_time_range(answer)
    )
    remote = graph_store.get_remote_task((pending.graph_run_id, pending.node_id))
    a2a.SendMessage(
        interface=remote.interface,
        credential=credential_for(remote.interface, requester),
        message=Message(
            messageId=pending.reply_message_id,
            role=ROLE_USER,
            contextId=remote.context_id,
            taskId=remote.task_id,
            parts=[DataPart({"time_range": pending.answer})],
        ),
        configuration={"returnImmediately": True},
    )
    interaction_store.mark_delivered(interaction_id)
    schedule_node_wakeup((pending.graph_run_id, pending.node_id), now=True)


# 远端 Agent 一侧：保存自己的 Task；Graph 无须知道内部工具与模型。
def server_SendMessage(request, caller):
    authorize(caller, skill="diagnose_api_latency")
    if request.message.taskId:
        task = load_task_for_caller(request.message.taskId, caller)
        if not reply_already_applied(task, request.message.messageId):
            require_state(task, TASK_STATE_INPUT_REQUIRED)
            apply_reply_and_enqueue_atomically(
                task, request.message.messageId,
                parse_time_range(request.message.parts)
            )
        return Task(task)

    request_id = request.metadata["clientRequestId"]
    task = create_or_load_task_and_enqueue_atomically(
        caller, request_id, request.message
    )
    return Task(task)


def server_execute(task_id):
    task = load_task(task_id)
    if task.input.time_range is None:
        set_status(task, TASK_STATE_INPUT_REQUIRED,
                   message="请确认分析最近一小时还是最近一天？")
        return
    try:
        metrics = monitoring.read_metrics(task.input.service, task.input.time_range)
        logs = monitoring.read_logs(task.input.service, task.input.time_range)
        report = diagnose_with_evidence(metrics, logs)
        save_artifact_and_complete_atomically(task, name="diagnosis", data=report)
    except DiagnosticError as error:
        set_status(task, TASK_STATE_FAILED, message=safe_error_summary(error))
```

这次运行在业务日志中应能串成一条线：`G42 / diagnose_latency` 提交消息 → 远端返回 `contextId=C1、taskId=T9` → `T9` 进入 `INPUT_REQUIRED` → 对话控制器记录问题 `Q17 → T9` → 用户回答 `Q17` → 同一 `T9` 恢复为 `WORKING` → 远端保存诊断 Artifact 并完成 → Graph 校验 Artifact 后进入 `summarize`。

这个例子有三个关键边界。**第一，**Graph 保存 `graph_run_id → taskId` 映射；远端 Agent 保存 Task 及其局部上下文。**第二，**用户回答带着交互归属回到原 Task，Graph 只在节点状态改变时继续调度。**第三，**`clientRequestId` 去重、持久入队、节点唤醒和 Artifact 校验属于应用契约；A2A 提供 Task 与消息语义，不保证这些业务行为自动成立。示例中的“原子创建并入队”可由同库事务加 Outbox 实现，避免 Task 已保存却未被执行。

如果首次 `SendMessage` 已在远端创建 Task、但响应在网络中丢失，调用方手里还没有 `taskId`。只有双方实现了上述按 `clientRequestId` 原子去重的约定，才可安全地用同一请求 ID 重试；否则应先对账，不能盲目创建第二个任务。节点超时时也应先请求 `CancelTask` 并查询最终状态，不能把“已请求取消”当作“副作用已撤销”。[发送与任务查询规范](https://a2a-protocol.org/v1.0.1/specification/)

### 5.2 Agent Card 如何交给模型做动态路由

模型不会自动获取 Agent Card。应用通过预配置地址、`/.well-known/agent-card.json` 或受控目录发现 Card，并保存在 Agent Registry 中。A2A 规范定义 Card 的身份、技能、输入输出类型、接口和认证字段；**“哪些 Agent 值得信任、当前用户可调用谁、是否允许传递这类数据”是应用策略**，需要在模型选择前检查。[Agent Card 字段与发现方式](https://a2a-protocol.org/v1.0.1/specification/)

| 步骤 | 负责方 | 实际处理 |
| --- | --- | --- |
| 发现与登记 | 应用 | 从允许的来源取得 Card，校验结构、来源和协议版本；按需缓存并记录版本 |
| 硬条件筛选 | 程序 | 核查授权、数据边界、支持的接口、输入输出类型和必要的协议能力 |
| 语义匹配 | 模型（可选） | 比较 Subgoal 与候选技能的描述、标签和示例，输出候选 ID |
| 选择复核 | 程序 | 确认 ID 属于筛选结果、技能属于该 Card，并重新检查调用策略 |
| 执行与观测 | A2A Client / Graph | 读取完整 Card 连接远端；记录选择依据、Card 版本和实际结果 |

固定 Graph 节点、明确业务规则或只剩一个合格候选时，可直接由程序选定。多个 Agent 的能力描述有语义差异、规则难以准确区分时，模型才承担“哪一个更适合当前 Subgoal”的判断。Agent Card 中的 `skills[].description`、`tags` 和 `examples` 适合用于这种比较；`supportedInterfaces`、`securityRequirements` 等字段主要由程序处理。[Agent Skill 与接口字段](https://a2a-protocol.org/v1.0.1/specification/)

给模型一份**精简的候选能力清单**即可。例如当前 Subgoal 是“分析订单接口延迟”，模型看到的输入可以是：

```json
{
  "subgoal": "只读分析订单接口最近一小时延迟升高的原因",
  "candidates": [
    {
      "agent_id": "diagnosis-agent",
      "skill_id": "diagnose_api_latency",
      "description": "分析指标和日志，输出带证据的 API 延迟诊断结论"
    },
    {
      "agent_id": "report-agent",
      "skill_id": "write_report",
      "description": "把已有结论整理成报告"
    }
  ]
}
```

这份清单可由应用直接放进一次模型调用的上下文，也可以由 `list_available_agents` 这类应用工具按需返回。候选很多时，先用注册表的标签或检索能力缩小范围，再交给模型比较。模型只返回结构化结果，例如 `{"agent_id":"diagnosis-agent","skill_id":"diagnose_api_latency","reason":"能直接分析指标和日志"}`；允许返回 `null` 表示没有合适候选。完整 Card、接口地址、凭证和调用主体身份由应用保存并使用，不必放进模型上下文。

```python
# 动态路由发生在 5.1 节的首次 SendMessage 之前。
def select_remote_agent(subgoal, requester):
    cards = agent_registry.load_allowed_cards()  # 来源受控，保留版本快照
    eligible = filter_skill_candidates_by_policy_and_protocol(
        cards, requester=requester,
        data_class=subgoal.data_class,
        input_mode=subgoal.input_mode,
        output_mode=subgoal.output_mode,
    )  # 每项含 agent_id、skill_id、card_ref、card_revision
    if not eligible:
        return NO_MATCH
    if len(eligible) == 1:
        selected, reason = eligible[0], "唯一合格候选"
    else:
        summaries = project_skill_summaries(eligible)  # 只含 ID 和能力描述
        choice = model.choose_json(
            goal=subgoal.text,
            candidates=summaries,
            instruction="只从候选 ID 中选择；无法判断时返回 null",
        )
        if choice is None or choice.agent_id is None:
            return NO_MATCH
        selected = require_candidate_and_skill(choice, eligible)
        reason = choice.reason
    recheck_policy(selected, requester, subgoal)  # 调用前再次校验
    trace_agent_choice(
        subgoal, selected.agent_id, selected.skill_id,
        selected.card_revision, reason
    )
    return selected
```

这套模型路由是应用设计，不是 A2A 规范要求。这里的 `agent_id` 是应用 Registry 的稳定键，`card_revision` 是 Registry 保存的版本或内容哈希；它们都不是 Agent Card 的标准字段。若启用动态路由，用 `select_remote_agent(...)` 的返回值替换 5.1 节固定的 `agent_id` 与 Card 查找，并把所选 Agent、技能和 Card 修订标识一起保存到 Graph 运行记录中。

Card 的描述是远端发布的数据，应作为**待比较的资料**进入模型，而不能让其中的文字改变系统指令或扩大权限。模型返回的 ID 也只是候选建议；程序用已筛选的 Registry 映射到真实接口，拒绝陌生 ID、已过期 Card 或越权选择。Card 声明某项技能只代表服务方的能力声明，实际成功率需要通过任务结果与评测持续验证。[Agent Card 规范](https://a2a-protocol.org/v1.0.1/specification/)

## 6. A2A、MCP、API 与任务队列的关系

| 机制 | 主要回答的问题 | 典型用途 |
| --- | --- | --- |
| **A2A** | 如何与独立 Agent 委托、对话并跟踪任务？ | 跨团队诊断 Agent、外部专业 Agent |
| **MCP** | Agent 如何发现并使用工具与资源？ | 查询数据库、调用业务 API、读取文档 |
| **普通 API** | 如何调用一个明确的服务操作？ | 固定输入输出的同步能力 |
| **任务队列** | 如何分发、缓冲和重试后台工作？ | 高吞吐、异步执行和背压 |

这四者可以组合使用。例如 Graph 用 A2A 调用远端诊断 Agent；诊断 Agent 用 MCP 连接监控工具；远端服务内部用任务队列调度执行。A2A 不替代 Graph 的控制流，也不自动提供任务队列的持久投递能力。[A2A 与 MCP](https://a2a-protocol.org/latest/topics/what-is-a2a/)

## 7. 落地时的可靠性与安全边界

- **认证与授权：**生产环境使用加密连接，按 Agent Card 声明的方式传递凭证。远端服务必须针对请求主体和具体操作独立授权；“Agent 声明有某项技能”不表示调用方拥有该技能的使用权限。[安全规范](https://a2a-protocol.org/v1.0.1/specification/)
- **重复与恢复：**记录本地运行 ID 与远端 `taskId`。网络超时后先查询任务状态，再决定是否重新提交；外部写操作还要设计业务幂等键和最终状态核对。
- **进度可靠性：**流式状态消息不应成为唯一事实来源；断线或收到 Webhook 后用 `GetTask` 核对。Webhook 接收方应去重，规范允许重复投递。[推送规范](https://a2a-protocol.org/v1.0.1/specification/)
- **输入与产物：**只传完成 Subgoal 所需的数据；对远端 Artifact 做格式、来源和业务规则校验，再写入 Graph State。远端 Agent 的自然语言结论不应直接提升为已验证事实。
- **取消与超时：**调用 `CancelTask` 是取消请求，不能假定副作用已经回滚。由业务系统核查实际状态，再确定 Graph 的后续动作。[取消操作](https://a2a-protocol.org/v1.0.1/specification/)

## 8. 最小动手练习

用一个“只读日志摘要 Agent”练习即可，不必先构建多 Agent 平台：

1. 为远端 Agent 发布 Agent Card，声明“按服务与时间范围汇总日志”技能、接口和认证要求。
2. 实现接收 Message、创建 Task、查询 Task 和返回摘要 Artifact。
3. 编写 Client：读取 Agent Card，提交一个诊断请求，保存 `taskId`，查询直到完成并读取 Artifact。
4. 加入一个 `INPUT_REQUIRED` 案例：缺少时间范围时提问，Client 用原 `taskId` 补充信息。
5. 验证任务失败、重复提交、断线后查询、无权限请求四条路径。

完成后应能回答：**谁拥有任务状态？哪个 ID 用来恢复远端任务？Graph 在什么条件下接受 Artifact 并继续？**

## 官方资料

- [A2A v1.0.1 规范](https://a2a-protocol.org/v1.0.1/specification/)：对象、操作、状态、接口与安全要求。
- [A2A 核心概念](https://a2a-protocol.org/latest/topics/key-concepts/)：Agent Card、Message、Task、Part 和 Artifact。
- [Task 生命周期](https://a2a-protocol.org/latest/topics/life-of-a-task/)：Message 与 Task 的选择、`contextId` 与 `taskId`。
- [Agent 发现](https://a2a-protocol.org/latest/topics/agent-discovery/)：Agent Card 的发现方式与内容。
