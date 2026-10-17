# Agent Graph Engineering：从图设计到生产运行

**版本：**2026-09-24　｜　**定位：**面向 Agent 产品、研发、架构、平台与质量团队的工程实战手册

> **体系导航：**[学习地图](<../README.md>)｜[Agent Loop](<../基础机制/01-Agent如何运行：Loop.md>)｜[Goal 与 Planning](<../基础机制/03-如何定义目标与计划.md>)｜[Agent Graph](<01-什么时候需要Agent Graph.md>)｜[Agent Harness](<../运行与连接/01-Agent Harness负责什么.md>)

> **一句话定义：**Agent Graph Engineering 是把 Agent 的状态图从概念或 Demo，工程化为可测试、可恢复、可审计、可演进的生产系统的方法与实践。

本文不重复介绍 Agent Graph 市场全景，而是回答一个更工程化的问题：**一张 Agent Graph 应该怎样被设计、实现、验证、部署、运行和维护？**

> **关于代码示例：**本文正文的代码统一使用 **LangGraph（Python）** 举例，因为它的 State / Node / 条件边 / checkpoint / interrupt 抽象与本文的工程概念几乎一一对应，最利于把“概念”落到“可写的代码”。这些片段用于说明设计，尚未在一个固定依赖版本的完整项目中统一执行；不要把它们当作可直接复制运行的工程。接入前需固定依赖并核对[官方 Graph API 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)。第二十章的框架选型保持多框架中立，不代表只能用 LangGraph。所有标注为“参考数量级”的阈值均非标准，需按业务压测校准。

## 阅读入口

- **首次阅读：**[四、从业务问题到 Graph 的设计过程](#四从业务问题到-graph-的设计过程) → [五、State Engineering：把任务事实设计成接口](#五state-engineering把任务事实设计成接口) → [六、Node Engineering：节点是责任和失败边界](#六node-engineering节点是责任和失败边界) → [七、Edge 与控制流工程](#七edge-与控制流工程)。
- **进阶运行与协作：**[6.3 Worker Agent 缺少信息时：局部探索与全局协调](#63-worker-agent-缺少信息时局部探索与全局协调) → [6.4 统一对话框下的多 Session 与 Worker Human-in-the-loop](#64-统一对话框下的多-session-与-worker-human-in-the-loop) → [十二、Persistence、恢复与副作用](#十二persistence恢复与副作用)。
- **组装与验证：**[十八、贯穿案例：把权限申请图工程化](#十八贯穿案例把权限申请图工程化) → [二十三、组装示例：权限申请图的实现骨架](#二十三组装示例权限申请图的实现骨架) → [十四、测试与评测工程](#十四测试与评测工程)。

## 一、一页结论

- **Agent Graph 是工程产物，Agent Graph Engineering 是建造方法。**前者是一张带状态的执行图；后者覆盖需求建模、状态设计、节点契约、运行时、测试、安全、部署和演进。
- **先画确定性 Workflow，再标出模型判断点。**不要从“需要几个 Agent”开始，而要从业务结果、不可确定部分和风险动作开始。
- **State 是核心接口。**Graph 是否可维护，首先取决于状态是否小、明确、有版本，并能区分任务事实、模型 Context 和最终业务事实。
- **节点是责任边界，不是 Prompt 数量。**节点应围绕稳定业务能力划分，并定义输入、输出、副作用、权限、超时、重试和成功条件。
- **Worker 负责局部信息探索和本地人工问答，Graph 负责全局协调。**已授权的只读查询及当前 Subgoal 内的用户补充可由 Worker 处理；Goal 变更、跨 Worker 依赖、权限审批和全局共享事实由 Graph 协调。统一对话框通过确定性的路由器连接多个 Session，不要求主 Agent 转发每条消息。
- **Loop 用于局部探索，Graph 用于宏观控制。**开放搜索和动态工具选择可以放进受限 Loop；审批、交易、恢复和高风险动作必须由 Graph 与程序控制。
- **checkpoint 不等于 exactly-once。**状态可以恢复，外部系统的写操作却可能已经发生，仍然需要幂等、执行记录、补偿和执行后验证。
- **生产质量不能只看最终回答。**必须同时评估任务结果、执行轨迹、工具副作用、权限边界、延迟与成本。
- **Graph 也需要版本和迁移。**节点、边、State、Prompt、模型和工具都可能变化，必须能够判断哪些运行中的任务可以继续、回放或回滚。

## 二、它与 Agent Graph、Harness Engineering 的区别

| 概念 | 关注对象 | 核心问题 |
| --- | --- | --- |
| Agent Graph | State、Nodes、Edges、循环、并行和暂停点 | 任务按照什么结构运行 |
| Agent Graph Engineering | Graph 的完整工程生命周期 | 如何把图做得可靠、可测、可维护 |
| Harness Engineering | 模型周围的执行环境与反馈系统 | 模型输出如何被安全执行、观察和持续改进 |
| Context Engineering | 每次模型调用的工作集 | 当前节点应该让模型看到什么 |
| Workflow Engineering | 确定性业务流程和规则 | 如何稳定执行已知步骤与异常路径 |

```text
AI Agent Engineering
├── Model / Prompt / Parameters
├── Context Engineering
├── Harness：Loop、工具执行、权限、沙箱、追踪、预算
├── Agent Graph Engineering：State、Nodes、Edges、恢复、迁移
├── RAG / Memory / 数据工程
├── 传统后端：API、数据库、事务、队列、IAM
└── Evals / Observability / 安全 / 运维
```

Agent Graph Engineering 通常是 Harness Engineering 的一部分，但并不是所有 Agent 都需要显式 Graph。简单问答只需一次模型调用；短期开放任务可能只需受限 Tool Loop；只有复杂状态、多阶段、长任务和高风险控制出现时，Graph 的工程价值才明显。

## 三、Agent Graph Engineering 应交付什么

工程化不是“画出一张流程图”就结束。一个可以交付的 Graph 至少应包含以下产物：

| 产物 | 回答的问题 |
| --- | --- |
| 业务结果说明 | 什么业务事实发生变化才算成功？如何验证？ |
| Graph 结构图 | 有哪些阶段、分支、循环、暂停点和结束条件？ |
| State Schema | 任务需要保存哪些事实、阶段和错误？谁可以修改？ |
| Node Contract | 节点的输入、输出、副作用、权限、超时和成功条件是什么？ |
| Session 与交互路由契约 | Worker 的 Session 如何关联任务？用户回复如何送回原 Worker？ |
| Tool Contract | 工具参数如何校验？是否写数据？能否幂等、补偿和审计？ |
| Context Contract | 模型能看到哪些信息？来源、时效、权限和 Token 预算是什么？ |
| 风险与审批矩阵 | 哪些动作自动执行，哪些需要审批，哪些必须禁止？ |
| 失败恢复图 | 每类错误重试、降级、暂停、补偿还是人工接管？ |
| 评测集与指标 | 正常、失败、边界和恶意输入如何验证？ |
| 运行手册 | 如何暂停、恢复、取消、回滚、排障和处理积压？ |
| 版本与迁移说明 | 旧任务如何在新 Graph、State、Prompt 或工具版本上继续？ |

## 四、从业务问题到 Graph 的设计过程

### 4.1 先定义结果，不要先选择框架

第一个问题不是“用 LangGraph 还是其他框架”，而是：

- 触发任务的事件是什么？
- 最终必须改变或确认哪个业务事实？
- 人工现在如何完成，基线质量、时间和成本是多少？
- 哪些步骤存在模糊判断，哪些步骤必须确定执行？
- 错误是否可逆？最坏损失是什么？谁承担责任？

### 4.2 先画普通 Workflow

先假设没有模型，画出确定性业务流程。然后将自然语言理解、动态检索、归纳、方案生成等不适合硬编码的部分标为模型判断点。

```text
业务流程：接收 → 校验 → 查询 → 决策 → 审批 → 执行 → 验证

模型适合：意图抽取、文本归纳、动态检索、候选方案
程序负责：身份、金额、权限、库存、规则、写操作、最终验证
```

### 4.3 选择最小控制方式

| 任务特征 | 优先形式 |
| --- | --- |
| 一次输入、一次输出 | 单次模型调用 |
| 短任务，需要动态调用几个工具 | 受限 Tool Loop |
| 步骤和规则固定 | 确定性 Workflow / BPM |
| 多阶段、状态复杂、需要恢复或审批 | 混合 Agent Graph |
| 职责、权限、上下文或并行必须隔离 | 在 Graph 中引入多个专业 Agent |

## 五、State Engineering：把任务事实设计成接口

### 5.1 四类信息必须分开

| 信息类型 | 用途 | 示例 |
| --- | --- | --- |
| Graph State | 保存任务阶段、共享事实和中间结果 | 风险等级、审批状态、重试次数 |
| Model Context | 一次模型调用的临时工作集 | 本节点指令、相关规则、必要历史 |
| Memory / RAG | 跨任务信息或按需检索的外部知识 | 用户偏好、政策文档、产品手册 |
| 业务事实 | 由权威系统保存的最终真实状态 | 订单、审批单、实际权限、支付结果 |

Graph State 不应复制整个聊天历史、所有文档和全部工具输出。它应该像一个稳定 API：字段含义清楚、类型明确、支持版本，并且每个节点只读写最少字段。

### 5.2 一个可维护的 State 示例（类型定义片段）

本例使用 `TypedDict` 定义 LangGraph State；它描述类型，不会自行执行运行时数据校验。用 `Annotated[类型, reducer]` 声明字段合并规则；并发更新的冲突与处理方式见下方说明。

```python
import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

# --- 结构化子对象：模型输出必须先落到这些类型上，不能直接塞自然语言 ---
class AccessRequest(TypedDict):
    requester_id: str
    project_id: str
    requested_roles: list[str]
    justification: str

class RiskAssessment(TypedDict):
    level: str            # "denied" | "normal" | "high"，受限枚举
    reasons: list[str]
    confidence: float

# --- reducer：决定“新值如何合并进旧值” ---
def merge_retry(old: dict, new: dict) -> dict:
    merged = dict(old)
    for k, v in new.items():
        merged[k] = merged.get(k, 0) + v   # 按节点累加重试次数
    return merged

class AccessRequestState(TypedDict):
    # 版本字段：第一版就要加，否则将来无法判断旧 checkpoint 能否恢复
    schema_version: str
    graph_version: str
    run_id: str

    # 任务事实：结构化、可校验
    request: AccessRequest
    missing_fields: list[str]
    proposed_roles: Optional[list[str]]
    risk: Optional[RiskAssessment]
    approval_status: str          # "pending" | "approved" | "denied"

    # 引用而非大对象：文档/证据只存 Artifact ID
    evidence_refs: list[str]

    # 并发安全字段：用 reducer 声明合并规则
    retry_count: Annotated[dict, merge_retry]      # 多节点各自累加
    errors: Annotated[list, operator.add]          # 多节点追加，不覆盖
```

**单次更新与并发更新要分开理解：**没有 reducer 时，单个更新通常替换该字段旧值；同一步的多个并行节点更新同一个不支持并发合并的字段，会触发 `INVALID_CONCURRENT_GRAPH_UPDATE`，不能假定“后写覆盖前写”。`Annotated[list, operator.add]` 定义列表追加的合并方式。是否需要追加、去重或拒绝冲突应按字段语义决定；追加 reducer 也不自动保证业务幂等。[官方并发更新说明](https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE)

### 5.2.1 判据：一个字段该不该进 Graph State？

State 是稳定接口，不是垃圾场。逐字段用下面这张表判断：

| 该字段满足… | 处理 |
|---|---|
| 后续节点的**路由或决策**依赖它 | ✅ 进 State（如 `risk.level`） |
| 是**跨节点共享的任务事实** | ✅ 进 State（如 `approval_status`） |
| 需要在 checkpoint 里**恢复**才能继续 | ✅ 进 State（如 `retry_count`） |
| 只是**某次模型调用的临时上下文** | ❌ 不进，属于 Model Context，用完即弃 |
| 是**大对象**（整篇文档、完整工具原始输出） | ❌ 存 Artifact，State 里只放 `xxx_ref` ID |
| 是**能从别的字段推导出来**的 | ❌ 不进，需要时现算，避免两份事实不一致 |
| 是**最终业务真相**（IAM 里的实际权限） | ❌ 不进，那属于权威系统；State 只存"我以为的"，验证时现查 |

### 5.3 State 设计原则

- 保存事实，不保存模糊叙述；模型输出先经过 Schema 校验。
- 保存引用，不复制大对象；文档和工具结果使用 Artifact ID。
- State 更新采用增量和明确所有权，避免多个并行节点任意覆盖同一字段。
- 敏感字段单独加密或只保存引用，不进入无关节点的 Context。
- 从第一版开始加入 `schema_version` 和 `graph_version`。
- 为每个字段定义来源、更新时间、可信度和最终权威系统。

## 六、Node Engineering：节点是责任和失败边界

节点不是“调用一次 LLM”的同义词。一个节点可以是普通函数、规则引擎、RAG、模型、工具、子图或人工审批。合理的节点通常对应稳定业务能力。

### 6.1 Node Contract 模板

| 字段 | 需要明确的内容 |
| --- | --- |
| Purpose | 节点只负责哪一项结果 |
| Reads / Writes | 读取和更新哪些 State 字段 |
| Context | 模型可见的信息、来源和 Token 预算 |
| Output Schema | 结构化输出类型和程序校验 |
| Side Effects | 是否修改外部系统，是否需要审批 |
| Timeout / Retry | 超时、重试条件、退避和最大次数 |
| Idempotency | 重复执行是否安全，幂等键如何生成 |
| Success | 如何客观证明节点完成 |
| Missing Information | 哪些信息允许 Worker 自查或本地询问用户，哪些必须返回 Graph 协调 |
| Failure Route | 重试、降级、补偿、暂停或人工接管 |
| Owner | 负责人、版本和告警接收人 |

### 6.1.1 一个节点在 LangGraph 里长什么样

节点就是一个 `(state) -> dict` 的函数：读若干 State 字段，返回**只包含它要更新的字段**的字典（LangGraph 会按 reducer 合并回去）。下面是一个模型节点（含结构化校验）和一个纯程序节点的对照：

```python
from pydantic import BaseModel, ValidationError

# 模型节点：抽取请求。注意——模型输出必须过 Schema，校验失败走错误路由，不能污染 State
class ExtractedRequest(BaseModel):
    requested_roles: list[str]
    justification: str

def extract_request(state: AccessRequestState) -> dict:
    raw = state["request"]["justification"]
    llm_out = call_llm(EXTRACT_PROMPT, raw)          # 只喂本节点需要的输入
    try:
        parsed = ExtractedRequest.model_validate_json(llm_out)
    except ValidationError as e:
        # 失败不抛异常污染全图，而是写入 errors 字段，由条件边决定重试/人工
        return {"errors": [{"node": "extract_request", "detail": str(e)}]}
    return {"request": {**state["request"], "requested_roles": parsed.requested_roles}}

# 纯程序节点：确定性风险判断。身份/金额/权限这类绝不交给模型
def deterministic_risk_check(state: AccessRequestState) -> dict:
    roles = state["proposed_roles"] or []
    if any(r in ADMIN_ROLES for r in roles):
        level = "high"
    elif violates_separation_of_duty(state["request"]["requester_id"], roles):
        level = "denied"
    else:
        level = "normal"
    return {"risk": {"level": level, "reasons": [...], "confidence": 1.0}}
```

**要点**：模型节点的产出**先校验再写 State**；确定性判断（风险分级）用普通 Python，不进模型。这两条决定了后面条件边能不能信任 State。

### 6.2 节点粒度

**过粗：**一个节点完成理解、检索、审批和执行，无法单独测试或恢复。
**过细：**每个 Prompt、工具和字段都成为节点，图快速膨胀。
**推荐：**以稳定业务阶段、权限边界、副作用边界和独立恢复点划分节点。

### 6.2.1 拆 / 合的硬触发条件

“推荐以业务边界划分”太抽象。下面是**出现即拆**的硬性信号——命中任意一条，就该把当前节点拆开：

| 命中信号 | 为什么必须拆 |
|---|---|
| 节点内出现**第 2 个不可逆副作用**（如既扣款又发信） | 崩溃恢复时无法只重放其中一个，幂等失控 |
| 节点内跨越了**权限边界**（先用普通身份查询、又用管理员身份写入） | 无法按最小权限单独授予，审计说不清 |
| 节点内既有**模型判断**又有**高风险写操作** | 模型的不确定性会直接触发真实副作用，无法在两者之间插入审批 |
| 你想为其中一段**单独设重试/超时**，另一段不需要 | 重试策略无法差异化，要么全重试要么全不重试 |
| 你想在中间**插一个 checkpoint / 人工审批点** | 恢复点只能落在节点边界上，节点太粗就没有落点 |

反过来，**出现即合**的信号：两个节点永远顺序执行、之间没有分支、没有独立恢复价值、共享同一份上下文——那就是被过度拆分，合并回去。

### 6.2.2 反面案例：巨型节点重构（before / after）

**before —— 一个 `handle_request` 节点包办一切：**

```python
def handle_request(state):
    parsed = call_llm(...)                     # ① 模型理解
    policy = vector_search(parsed.roles)       # ② 检索
    proposal = call_llm(policy, parsed)        # ③ 模型生成方案
    if is_high_risk(proposal):                 # ④ 风险判断
        approved = wait_for_manager()          # ⑤ 阻塞式审批（无法 checkpoint）
    iam_client.grant(proposal)                 # ⑥ 高风险写入
    notify(state["requester_id"])              # ⑦ 第二个副作用
    return {"done": True}
```

问题全踩齐了：无法单测任一步；⑤是阻塞等待，进程一崩审批状态全丢；⑥⑦两个副作用挤在一起，恢复时要么重复授权要么重复发信；模型判断③紧挨高风险写入⑥，中间插不进审批。

**after —— 按副作用边界、权限边界、恢复点拆开：**

```text
extract_request      # 模型：只理解
  → retrieve_policy    # 检索：只读
  → propose_access     # 模型：只生成候选，无副作用
  → risk_check         # 程序：确定性分级 —— 恢复点/审批点落在这里
  → approval           # interrupt 暂停，状态存 checkpoint
  → grant_access       # 唯一的高风险写入，带幂等键
  → notify             # 第二个副作用独立成节点，可单独重试
```

每个节点现在都能单测、单独设重试、单独 checkpoint，审批天然落在 `risk_check` 与 `grant_access` 之间。

### 6.3 Worker Agent 缺少信息时：局部探索与全局协调

当一个 Node 由 Agent Worker 执行时，它可能在工作过程中发现输入不足。局部信息由 Worker 在授权范围内收集；涉及全局目标、权限或其他节点时再升级给 Graph。推荐原则是：

> **局部探索下沉给 Worker，全局协调上收给 Graph。**

```text
Worker 缺少信息
      ↓
是否属于当前 Subgoal？
  ├─ 否 → 返回 Graph
  └─ 是
      ↓
是否能用已授权、低风险工具获得？
  ├─ 是 → Worker 在局部 Loop 中自行收集
  └─ 否
      ↓
是否只需用户补充当前 Subgoal 的信息？
  ├─ 是 → Worker 发出 human_input_required，等待答案直达原 Session
  └─ 否 → 返回 needs_information，由 Graph 协调
```

#### 6.3.1 信息责任判断表

| 缺失信息 | 责任方 | 原因 |
| --- | --- | --- |
| 当前 Worker 已授权访问的只读数据 | Worker | 属于局部探索，不必增加跨节点往返 |
| 完成当前 Subgoal 所需的领域资料 | Worker | Worker 最了解当前局部未知 |
| 已存在 Graph State，但没有传给 Worker | Graph / Context Builder | 不应让 Worker 重复查询已有事实 |
| 需要另一个专业 Worker 提供 | Graph | 需要显式依赖、权限、Trace 和恢复路径 |
| 用户补充当前 Subgoal 的信息 | Worker + 对话控制器 | Worker 保持本地 Human-in-the-loop；回答按交互 ID 直达原 Session |
| 涉及 Goal、范围或成功标准变化 | Graph / Goal Controller | Worker 无权修改任务契约 |
| 需要新增工具、提升权限或执行高风险动作 | Graph / Approval | 必须经过策略和审批 |
| 会被多个后续节点共同使用 | Graph State | 需要统一来源、去重和版本管理 |
| 成本高、风险高或包含写操作 | Graph / Runtime | 需要预算、幂等和副作用控制 |

#### 6.3.2 Worker 自己收集信息的局部 Loop

例如诊断 Worker 的目标是“找出 `order-api` 延迟升高的最可能原因”，并已经被允许使用：

```text
query_metrics
search_logs
get_deployments
```

如果它发现缺少连接池指标，可以在节点内部完成：

```text
读取已有指标
  ↓
发现缺少连接池数据
  ↓
调用已授权 query_metrics
  ↓
加入局部 Observation
  ↓
继续诊断
```

```python
def diagnosis_worker(task: WorkerTask):
    local_state = initialize_worker_state(task)

    while not local_state.done:
        missing = detect_missing_information(local_state)

        if missing:
            if can_collect_locally(missing, task):
                observation = call_allowed_tool(
                    missing.required_tool,
                    missing.arguments,
                )
                local_state.add_observation(observation)
                continue

            if can_ask_user_locally(missing, task):
                return suspend_for_local_human_input(
                    local_state,
                    missing,
                )

            return build_needs_information_result(
                local_state,
                missing,
            )

        decision = model_decide(local_state)

        if completion_criteria_met(decision, local_state):
            return build_completed_result(local_state)

        execute_local_action(decision, local_state)
```

`can_collect_locally` 至少检查：

```python
def can_collect_locally(missing, task):
    return (
        missing.belongs_to_current_subgoal
        and missing.can_self_collect
        and missing.required_tool in task.allowed_tools
        and missing.impact != "high"
        and missing.estimated_cost <= task.remaining_budget
        and not missing.requires_scope_change
        and not missing.requires_permission_change
    )
```

`can_ask_user_locally` 则要求问题只影响当前 Subgoal、Worker 契约允许人工补充、不需要改变 Goal 或权限，也不依赖其他节点；否则走 `needs_information` 升级路径。

#### 6.3.3 用 MissingInformation 显式声明需求

无法通过授权工具自查时，先判断问题归属。当前 Subgoal 内的用户补充由 Worker 发出本地 `human_input_required` 事件；需要 Graph 介入的请求才返回结构化 `MissingInformation`。Worker 不自行改变 Goal、扩大权限或调度其他 Worker：

```python
class MissingInformation(BaseModel):
    field: str
    reason: str
    scope: Literal["worker_local", "graph_global"]

    source: Literal[
        "state",
        "user",
        "tool",
        "worker",
        "permission",
    ]

    impact: Literal["low", "medium", "high"]
    can_self_collect: bool

    required_tool: str | None = None
    required_worker: str | None = None
    required_permission: str | None = None


class WorkerResult(BaseModel):
    status: Literal[
        "completed",
        "needs_information",
        "blocked",
        "failed",
    ]

    state_patch: dict
    evidence: list[str]
    missing_information: list[MissingInformation]
    continuation_state: dict | None = None
```

`MissingInformation` 可以作为 Worker 的内部判定对象；进入 `WorkerResult.missing_information` 的只应是 `scope=graph_global` 的升级请求。本地用户问题转换成 `human_input_required` 事件，归属仍在原 Worker Session。

例如环境不明确：

```json
{
  "status": "needs_information",
  "state_patch": {},
  "evidence": [],
  "missing_information": [
    {
      "field": "environment",
      "reason": "测试和生产环境对应不同数据源和权限",
      "scope": "graph_global",
      "source": "user",
      "impact": "high",
      "can_self_collect": false,
      "required_tool": null,
      "required_worker": null,
      "required_permission": null
    }
  ],
  "continuation_state": {
    "completed_local_steps": ["identify_service"],
    "current_hypotheses": []
  }
}
```

`continuation_state` 只保存 Worker 后续运行所需的局部进度；它必须受大小、敏感数据和版本约束。恢复是否重跑部分代码取决于运行时的 checkpoint 粒度，因此恢复路径仍需保证幂等。

#### 6.3.4 Graph 根据升级请求的来源路由

下面的路由只处理 `scope=graph_global` 的请求。`scope=worker_local` 的用户问答由第 6.4 节的对话控制器直接交给原 Worker Session，不进入这条 Graph 信息收集分支。

```text
worker
  ↓ needs_information
information_router
  ├─ source=state      → rebuild_worker_input
  ├─ source=user       → ask_user / interrupt
  ├─ source=tool       → information_collector
  ├─ source=worker     → specialist_worker
  └─ source=permission → approval_node
```

```python
def route_worker_result(result: WorkerResult) -> str:
    if result.status == "completed":
        return "validate_worker_result"
    if result.status == "failed":
        return "failure_handler"
    if result.status == "blocked":
        return "human_handoff"

    missing = result.missing_information[0]
    assert missing.scope == "graph_global"

    routes = {
        "state": "rebuild_worker_input",
        "user": "ask_user",
        "tool": "information_collector",
        "permission": "approval_node",
    }

    if missing.source == "worker":
        return validate_worker_route(missing.required_worker)

    return routes.get(missing.source, "human_handoff")
```

如果一次返回多个缺失项，Graph 可以按依赖、风险和成本分组：可并行的只读信息同时收集；需要用户或审批的项合并成一次交互；互相依赖的项按顺序处理。

#### 6.3.5 全局信息验证、写入 State 与恢复 Worker

外部收集结果不能直接拼进 Worker Prompt，应先成为带来源的候选事实：

```python
class CollectedFact(BaseModel):
    field: str
    value: object
    source: str
    observed_at: datetime
    confidence: float
    artifact_id: str | None = None
```

Graph 校验后更新共享 State：

```python
def merge_collected_information(state, result):
    fact = validate_collected_fact(result)

    return {
        "facts": [fact],
        "pending_information_request": None,
        "resume_node": state["suspended_worker_node"],
    }
```

Graph 协调的信息恢复路径：

```text
Worker 返回 needs_information
  ↓ checkpoint Worker continuation_state
收集 / 用户补充 / 审批
  ↓ 验证并写入 Graph State
更新原 Worker 的输入或 continuation
  ↓ 使用同一 worker_session_id、任务版本和恢复引用
恢复原 Worker
```

这条路径适用于跨节点或全局信息。Worker 本地问答只需把经验证的答案交回原 Session；只有确实影响其他节点的事实才写入 Graph State。如果 Worker 在等待前已经产生外部副作用，必须保存幂等键和执行凭证；恢复时先验证外部真实状态，不能盲目重放。

#### 6.3.6 默认禁止 Worker 横向调用其他 Worker

不推荐：

```text
diagnosis_worker
  → 私自调用 policy_worker
      → 再调用 database_worker
```

这种隐藏调用关系会导致：

- Graph 看不到完整依赖和执行路径；
- 权限、成本、超时和 Trace 难以统一管理；
- Worker 之间可能形成循环调用；
- checkpoint 和恢复边界不清晰；
- 同一信息被多个 Worker 重复收集；
- 用户不知道任务为何暂停或扩大范围。

推荐方式：

```text
diagnosis_worker
  → needs_information(required_worker="policy_worker")
  → Graph 校验并调度 policy_worker
  → 结果写入共享 State
  → Graph 恢复 diagnosis_worker
```

只有在提前定义、权限封闭、可观测的子图中，才允许一个 Supervisor Worker 管理固定范围内的子 Worker；这仍然应该表现为显式子图，而不是不可见的任意调用。

#### 6.3.7 局部 Context 与全局 State 的边界

Worker 收集的信息不是全部都要写入 Graph State：

| 信息类型 | 保存位置 |
| --- | --- |
| 临时搜索候选、无关日志片段、局部推理草稿 | Worker 局部 Context / 临时 Artifact |
| 影响最终结论的已验证事实 | Graph State，并保留来源和时间 |
| 大型日志、文档和原始工具结果 | Artifact Store，State 只保存引用和摘要 |
| 权限、审批、预算和执行凭证 | Graph / Harness 控制状态 |
| 未验证的模型推断 | 假设区，不得写成已确认事实 |

最终决策函数可以写成：

```python
def information_owner(missing, worker_contract, graph_state):
    if has_fact(graph_state, missing.field):
        return "graph_rebuild_input"

    if (
        missing.can_self_collect
        and missing.required_tool in worker_contract.allowed_tools
        and missing.impact != "high"
        and not missing.requires_scope_change
        and not missing.requires_permission_change
    ):
        return "worker"

    if missing.source == "user":
        if missing.scope == "worker_local":
            return "worker_ask_user"
        return "graph_ask_user"
    if missing.source == "worker":
        return "graph_route_worker"
    if missing.source == "permission":
        return "graph_request_approval"

    return "graph_information_collector"
```

工程上的最终边界是：

```text
Worker Agent
  负责当前 Subgoal、局部只读探索、本地 Human-in-the-loop、返回事实/证据/缺失信息
  不负责修改 Goal、扩大权限、直接调度任意 Worker

Graph / Supervisor
  负责全局用户交互、跨 Worker 协调、全局 State、权限审批、节点状态监督
  不应成为所有局部搜索的中央瓶颈
```

### 6.4 统一对话框下的多 Session 与 Worker Human-in-the-loop

一个用户对话框可以展示多个 Agent 的工作，但“统一展示”不等于“所有消息都先交给主 Agent”。对话控制器是应用程序中的确定性路由组件，负责把运行事件投影成用户消息，并把用户回复送到拥有该交互的 Session。

#### 6.4.1 四种标识与 Session 关联

```text
用户对话 conversation_id=C1
  └─ 任务运行 graph_run_id=G42
       ├─ 主 Agent Session=M7（如果需要规划或汇总）
       ├─ 诊断 Worker Session=W11
       └─ 权限 Worker Session=W12
```

| 标识 | 用途 | 保存内容 |
| --- | --- | --- |
| `conversation_id` | 统一对话框和用户可见消息流 | 用户消息、展示事件及其引用 |
| `graph_run_id` | 一次目标执行 | 全局 State、节点依赖和运行状态 |
| `worker_session_id` | Worker 自己的上下文与恢复入口 | 当前 Subgoal、局部消息和 checkpoint |
| `interaction_id` | 一次待回答的问题或审批 | 归属 Session、问题、状态和回复去重键 |

Session Registry 保存 `conversation_id → graph_run_id → worker_session_id` 的关联；Pending Interaction Registry 保存 `interaction_id → owner_session_id`。这些是路由和恢复索引，不需要把 Worker 的完整历史复制到主 Agent Session。主 Agent 只接收已完成的结构化结果，或确实需要全局决策的升级请求。

#### 6.4.2 Worker 本地问答：显示在同一对话框，答案直达原 Session

Worker 需要当前 Subgoal 内的补充信息时，发出事件并进入 `WAITING_FOR_HUMAN`：

```json
{
  "type": "human_input_required",
  "conversation_id": "C1",
  "graph_run_id": "G42",
  "worker_session_id": "W11",
  "interaction_id": "Q17",
  "question": "请确认要分析最近一小时，还是最近一天的延迟？",
  "expected_input": "time_range",
  "status": "WAITING_FOR_HUMAN"
}
```

用户在统一对话框回答时，客户端或对话控制器必须带上交互引用：

```json
{
  "conversation_id": "C1",
  "reply_to": "Q17",
  "answer": "最近一小时"
}
```

```text
Worker W11 → human_input_required(Q17)
  → 对话控制器展示问题、记录 Q17→W11
  → 用户回复 Q17
  → 对话控制器校验身份、归属、问题状态和输入格式
  → Worker Runtime 将答案送入 W11 的等待点
  → W11 继续当前任务；Graph 只更新该节点的粗粒度状态
```

对话控制器不会调用主 Agent 来转发这条消息。多个 Worker 同时提问时，界面应让用户明确回复哪张问题卡片；无法唯一确定归属的自由文本不能凭猜测路由。重复提交同一个 `interaction_id` 要去重，过期或已取消的问题应拒绝恢复。

#### 6.4.3 等待与恢复的真实含义

`WAITING_FOR_HUMAN` 对产品和调度仍有意义：它告诉系统谁在等用户、哪些并行节点可继续、Graph 何时汇合、如何超时或取消。它不要求主 Agent 再走一遍，也不表示创建新 Worker。一次模型调用结束后，等待状态由 Worker Runtime 保存；用户答复时，运行时使用原 Session 标识恢复执行。

| Worker 实现 | 用户答复后怎么继续 | 适用情况 |
| --- | --- | --- |
| 长生命周期 Actor | 唤醒同一 Worker 实例，并交付答案 | 运行时能可靠维护存活实例时 |
| 持久化 Session + checkpoint | 从同一 Session 的保存状态继续，可能重新启动执行进程 | 长时间等待、跨进程和故障恢复时 |
| 一次性 Worker | 以明确任务包和结果结束；若需多轮问答，另建可关联的 Session | 无需持续局部上下文的短任务 |

“恢复同一个任务”是业务语义，并不保证程序从 `interrupt` 之后的机器指令原地继续。以 LangGraph 的 `interrupt()` 为例，恢复时会从发生中断的节点开头重新执行，中断前的代码可能重跑；因此应把外部写操作拆到安全节点，或提供幂等键与执行凭证。详见[LangGraph 官方 Interrupts 文档](https://docs.langchain.com/oss/python/langgraph/interrupts)。

#### 6.4.4 对话投影与升级边界

对话控制器可以将 `assistant_message`、`progress`、`plan_update`、`human_input_required`、`approval_request`、`artifact`、`error`、`final` 等事件整理到同一消息流。普通视图只展示与用户有关的进度、问题和结果；调试视图再显示节点、Session 和 Trace。原始工具日志与 Worker 局部推理内容留在各自运行记录中。

Graph 只需同步 `RUNNING / WAITING_FOR_HUMAN / COMPLETED / FAILED / CANCELLED` 等节点状态及最终结果。以下情况由 Worker 发出升级请求，交给 Graph、Goal Controller 或审批策略处理：用户回答改变整体 Goal 或 Plan；需要其他 Worker；需要提升权限或执行高风险动作；答案与全局 State 冲突。升级完成后，Graph 再将必要的结果交给原 Worker Session。

因此职责是：**Worker 拥有局部问答；对话控制器负责展示与回传；Graph 监督任务依赖和全局状态；主 Agent 只在需要规划、重规划或最终汇总时参与。**

## 七、Edge 与控制流工程

### 7.1 常见边类型

- **固定边：**前一步完成后进入确定的下一步。
- **条件边：**根据结构化 State 或规则进行路由。
- **模型路由：**模型输出受限枚举，再由程序验证后路由。
- **循环边：**追问、重试、反思或工具探索。
- **并行边：**多个独立任务同时执行，之后聚合结果。
- **异常边：**超时、工具失败、验证失败和人工接管路径。

### 7.2 路由优先级

```text
确定性规则路由
    优先于
受限的模型分类路由
    优先于
开放式模型自主规划
```

能用类型、规则或业务状态决定的边，不应让模型决定。模型路由必须输出有限枚举、理由和必要证据；涉及高风险动作时，未知或低置信度应默认进入拒绝或人工审批路径。

### 7.3 条件边在 LangGraph 里的真写法

`add_conditional_edges` 接三个参数：**起点节点**、**路由函数**、**返回值到目标节点的映射**。路由函数读 State、返回一个字符串 key：

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(AccessRequestState)
builder.add_node("risk_check", deterministic_risk_check)
builder.add_node("manager_approval", manager_approval)
builder.add_node("security_approval", security_approval)
builder.add_node("explain_and_end", explain_and_end)

# 路由函数：只读结构化 State，不调用模型
def route_by_risk(state: AccessRequestState) -> str:
    return state["risk"]["level"]     # 已被约束为 "denied"|"normal"|"high"

builder.add_conditional_edges(
    "risk_check",
    route_by_risk,
    {
        "denied": "explain_and_end",
        "normal": "manager_approval",
        "high":   "security_approval",
    },
)
```

**关键**：这条边的判断来自 `risk_check`（确定性程序）写好的 `risk.level`，路由函数**不碰模型**。风险分级这种事，一旦交给模型在边上临时决定，就等于把"要不要走高风险审批"的控制权交了出去。

### 7.4 模型路由：必须"枚举 + 程序校验"双保险

有些边确实需要模型判断（如意图分类）。此时**模型的输出不能直接当路由 key**，要先约束成枚举、再由程序兜底：

```python
from enum import Enum

class Intent(str, Enum):
    NEW_ACCESS = "new_access"
    MODIFY = "modify"
    REVOKE = "revoke"
    UNKNOWN = "unknown"          # 必须有兜底枚举

def route_by_intent(state) -> str:
    raw = call_llm_with_enum(INTENT_PROMPT, state, allowed=Intent)
    try:
        intent = Intent(raw.strip())
    except ValueError:
        intent = Intent.UNKNOWN                 # 模型乱答 → 兜底
    if intent == Intent.UNKNOWN or state.get("low_confidence"):
        return "human_triage"                   # 未知/低置信 → 人工，绝不猜
    return intent.value
```

**三条铁律**：① 模型只能从**有限枚举**里选；② 程序**校验**返回值，非法值一律落到兜底分支；③ 涉及高风险动作时，`UNKNOWN` 或低置信度**默认走拒绝/人工**，而不是走某个"看起来最可能"的分支。

### 7.5 路由优先级的代码化判据

面对一条边，按这个顺序自问，能在上一层解决就绝不下沉到下一层：

| 先问 | 如果是 | 用 |
|---|---|---|
| 能用**类型/字段值/业务规则**唯一确定吗？ | 是 | 确定性 `add_conditional_edges` + 纯函数路由（7.3） |
| 必须靠**语义理解**分类，但选项**有限且可枚举**吗？ | 是 | 模型路由 + 枚举 + 程序校验（7.4） |
| 连有哪些选项都无法预先列出？ | 是 | 受限 Loop 里让模型规划（见第八章），**但结果仍要结构化写回 State 再路由** |

一句话：**规则能定的边不给模型；模型定的边必须能被程序否决。**

## 八、Loop Engineering：允许探索，但必须有边界

Loop 是 Agent 的微观执行机制。Graph 中的某个研究、诊断或编码节点可以运行 Tool Loop，但必须明确：

- 允许调用哪些工具，读工具和写工具是否分开；
- 最大模型轮次、工具次数、时间、Token 和费用；
- 什么结果表示完成，什么状态表示无进展；
- 连续失败、重复调用和相同结果如何检测；
- 何时压缩 Context，何时转人工或降级；
- Loop 结束后如何将结果结构化写回 Graph State。

```text
Graph：接单 → 诊断节点 → 风险校验 → 审批 → 执行 → 验证
                  │
                  └─ 诊断 Tool Loop：
                     观察 → 查询日志 → 读取结果 → 再判断 → 结束
```

### 8.1 一个受限 Tool Loop 的实现片段

Loop 通常写在**单个节点内部**：模型循环选工具，程序在每一圈强制检查预算和进展。核心是那几个"熔断"计数器——没有它们，Loop 会烧钱、打转或永不停止。

```python
# 参考数量级，非标准，需按业务压测校准
LOOP_LIMITS = {
    "max_turns": 8,          # 模型最多来回 8 轮
    "max_tool_calls": 15,    # 工具最多调 15 次
    "max_seconds": 60,       # 墙钟超时
    "max_tokens": 40_000,    # 累计 token 预算
    "max_usd": 0.50,         # 累计成本上限
}

def diagnosis_node(state: AccessRequestState) -> dict:
    budget = Budget(LOOP_LIMITS)
    seen_results = set()          # 用于检测"重复调用得到相同结果"
    no_progress = 0

    while True:
        # ① 每圈先查熔断，超限立即结构化收尾，不是抛异常
        if budget.exceeded():
            return _finish(state, status="budget_exceeded", partial=budget.summary())

        step = call_llm_react(DIAGNOSIS_PROMPT, state, tools=READ_ONLY_TOOLS)
        budget.charge(step)       # 累加 turns/tokens/usd

        if step.is_final:         # ② 模型自认完成 → 结构化写回
            return _finish(state, status="done", finding=step.finding)

        result = run_tool(step.tool_call, allowed=READ_ONLY_TOOLS)  # ③ 只允许读工具
        budget.count_tool()

        # ④ 无进展检测：同样的工具+参数拿到同样的结果，累计到阈值就退出
        fingerprint = (step.tool_call.name, step.tool_call.args_hash, result.hash)
        if fingerprint in seen_results:
            no_progress += 1
            if no_progress >= 2:
                return _finish(state, status="no_progress", partial=result)
        else:
            no_progress = 0
            seen_results.add(fingerprint)
```

### 8.2 阈值参考值（起点，不是标准）

没人能凭空给对，但需要一个**起点**去压测。下面是常见量级，务必按自己的任务校准：

| 维度 | 短诊断/检索类 | 复杂研究/编码类 | 说明 |
|---|---|---|---|
| max_turns（模型轮次） | 5–8 | 15–30 | 超过就该怀疑任务没收敛 |
| max_tool_calls | 10–15 | 30–60 | 读工具可放宽，写工具应单独更严 |
| max_seconds | 30–60 | 120–600 | 与用户是否在线等待强相关 |
| max_tokens | 20k–40k | 100k–200k | 触顶前应先触发 Context 压缩 |
| 无进展阈值 | 连续 2 次重复即停 | 连续 2–3 次 | 重复=相同工具+参数+结果 |

**四条边界原则**：① 读工具与写工具分开，Loop 内**默认只给读工具**，写操作交回 Graph 主流程审批；② 熔断触发是**结构化收尾**（写回 `status` 和已有部分结果），不是抛异常让全图崩；③ 触及 token 上限前先压缩 Context 再决定是否继续；④ Loop 结束**必须**把结果结构化写回 Graph State，不能把"模型脑子里的中间态"留在 Loop 里。

## 九、Context 与 Prompt 的节点级工程

每个模型节点都应该拥有独立的 Context Contract，而不是把完整 State 和历史全部传入模型。

```text
固定节点指令
+ 当前任务请求
+ State 中本节点必要字段
+ 按需检索的知识与业务事实
+ 必要的近期工具结果
- 与当前职责无关的历史
- 未授权敏感信息
- 不可信内容中的指令
= Node Context
```

### 9.1 Context 质量检查

- 相关性：每条信息是否影响当前节点决策？
- 来源：是否保留文档、系统、版本和时间戳？
- 权限：当前用户与节点是否允许看到这些数据？
- 冲突：多条事实冲突时使用哪个权威来源？
- 预算：超出 Token 限制时按什么规则压缩或检索？
- 注入边界：外部内容被视为数据，而不是系统指令。

## 十、Tool Engineering：把模型意图变成安全行动

工具是模型进入真实世界的边界。工具名称和描述决定模型能否正确选择；Schema 和权限决定错误是否会成为真实副作用。

### 10.1 工具分级

| 级别 | 示例 | 默认控制 |
| --- | --- | --- |
| 只读 | 搜索、查询订单、读取日志 | 身份与数据范围过滤 |
| 可逆写入 | 创建草稿、添加标签、生成工单 | 参数校验、幂等、审计、必要确认 |
| 高风险写入 | 支付、退款、授权、发信、删除数据 | 确定性规则、人工审批、最小权限、执行后验证 |
| 不可逆或外部影响 | 生产删除、法律承诺、公开发布 | 默认禁止或强制双人审批 |

### 10.2 Tool Contract 必备字段

工具应定义调用者身份、输入 Schema、权限范围、超时、重试、幂等键、返回类型、错误分类、审计字段和补偿方式。MCP 可以标准化工具发现与调用，但不会替 Graph 决定何时调用，也不会自动完成业务授权。

## 十一、Runtime 与 Harness Engineering

Graph 描述控制结构，Runtime/Harness 执行并强制约束。生产运行时至少需要：

- 运行 ID、线程或任务 ID、State Store 和 checkpoint；
- Worker Session Registry、待答交互索引及统一对话框的事件投影；
- 事件调度、队列、并发限制、取消、超时和背压；
- 模型适配、Prompt 版本、工具注册和结果解析；
- 身份传播、工具权限、沙箱、审批和预算；
- 节点生命周期事件、Trace、指标、日志和 Artifact；
- 失败分类、重试、降级、恢复、补偿和 kill switch。

简单 Graph 可以进程内运行；长任务、人工审批、高并发或跨系统流程通常需要持久化运行时和异步 Worker。不要把进程内内存当作生产 State Store。

## 十二、Persistence、恢复与副作用

### 12.1 checkpoint 保存什么

- Graph 与 State 版本；
- 已完成节点和下一执行位置；
- 节点输出、错误和必要 Artifact 引用；
- 等待的人工输入或外部事件；
- 待答交互的 `interaction_id`、归属 Session 和回复状态；
- 模型、Prompt、工具与策略版本。

### 12.1.1 checkpointer 在 LangGraph 里怎么配

checkpointer 是恢复和人工审批的**前提**——没有它 `interrupt()` 无法工作。开发用内存版，生产必须换成持久化版（Postgres/SQLite），并在每次调用时传 `thread_id` 标识要读写的持久化线程；一次线程可以包含多次调用：

```python
# 开发：进程内，重启即丢，绝不能上生产
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# 生产：持久化到 Postgres（import 路径随版本，以官方为准）
# from langgraph.checkpoint.postgres import PostgresSaver
# checkpointer = PostgresSaver.from_conn_string("postgresql://...")

app = builder.compile(checkpointer=checkpointer)

# 本例让一个任务独占一个 thread；恢复时继续使用该 thread_id
config = {"configurable": {"thread_id": state["run_id"]}}
app.invoke(initial_state, config=config)
```

### 12.2 为什么 checkpoint 不等于 exactly-once：一次故障的秒级回放

很多人以为"有了 checkpoint 就不会重复执行"。错。checkpoint 保护的是**状态**，保护不了**已经发生的外部副作用**。看这条真实时间线：

```text
T+0.0s  进入 grant_access 节点
T+0.1s  调用 iam_client.grant(role)  ── 请求已发出
T+0.3s  IAM 返回 success，权限"张三=admin"已真实写入 IAM  ← 副作用已发生
T+0.4s  准备写 checkpoint……
T+0.4s  ✗ 进程 OOM / Pod 被驱逐 / 机器崩溃      ← checkpoint 还没落盘！
────────────────────  恢复  ────────────────────
T+8.0s  运行时按最后一个成功 checkpoint 恢复
        → 最后成功的是 grant_access 之前的那个
        → 图认为 grant_access "还没执行"，于是重新进入
T+8.1s  再次调用 iam_client.grant(role)      ← 重复授权！
```

问题的根源：**副作用（T+0.3s）发生在 checkpoint 落盘（T+0.4s 失败）之前**。恢复靠的是最后一个成功 checkpoint，它不知道那 0.1 秒里已经写过 IAM 了。

### 12.2.1 幂等键：让"第二次"变成安全的空操作

解法不是"更快地写 checkpoint"（永远有那个时间窗），而是让**同一个操作重复执行也只生效一次**：

```python
def make_idempotency_key(state, node_id, business_object_id, operation) -> str:
    # 同一次运行、同一节点、同一业务对象、同一操作 → 恒定同一个键
    return f"{state['run_id']}:{node_id}:{business_object_id}:{operation}"

def grant_access(state: AccessRequestState) -> dict:
    key = make_idempotency_key(
        state, "grant_access",
        business_object_id=state["request"]["requester_id"],
        operation="grant:" + ",".join(state["proposed_roles"] or []),
    )

    # ① 先查这个幂等键是否执行过（存在自己的执行记录表里）
    prior = execution_log.get(key)
    if prior is not None:
        return {"execution": {"status": "already_done", "op_id": prior["op_id"]}}

    # ② 恢复时不轻信本地状态，先查最终业务真相
    if iam_client.has_roles(state["request"]["requester_id"], state["proposed_roles"]):
        execution_log.put(key, {"op_id": "recovered", "verified": True})
        return {"execution": {"status": "verified_existing"}}

    # ③ 真正执行，并记录外部系统返回的业务操作 ID
    result = iam_client.grant(
        state["request"]["requester_id"], state["proposed_roles"],
        idempotency_key=key,        # 若外部 API 自身支持幂等键，一并传下去
    )
    execution_log.put(key, {"op_id": result.op_id})
    return {"execution": {"status": "granted", "op_id": result.op_id}}
```

四道防线：① 本地执行记录先拦一次；② 恢复时**查最终业务状态**而非信本地；③ 记录外部返回的业务操作 ID 供审计；④ 把幂等键透传给支持它的外部 API。**不能幂等的操作**（如"发送不可撤回的邮件"）必须改设计——要么拆成"先落草稿再确认发送"，要么配补偿/人工流程。

## 十三、并行与分布式执行

Map–Reduce、Supervisor–Worker 和多文档处理常需要并行。并行工程必须明确：

- 分支是否真正独立，是否访问相同外部资源；
- State Reducer 如何合并更新，冲突如何处理；
- 部分成功、部分失败时继续、回滚还是等待；
- Worker 重复领取任务如何幂等；
- 并发量、模型限流、工具配额和下游背压；
- 聚合节点如何处理缺失、重复和顺序不确定的结果。

多 Agent 只是并行与职责隔离的一种组织方式。只有知识、权限、上下文或并行能力确实需要隔离时才拆分；否则会增加消息传递、上下文复制、延迟、成本和评测难度。

## 十四、测试与评测工程

### 14.1 五层测试

| 层级 | 验证内容 |
| --- | --- |
| Node Unit Test | 固定输入下的 State 更新、Schema、错误和副作用 |
| Route Test | 正常、边界和恶意输入进入正确分支 |
| Tool Contract Test | 参数、权限、超时、幂等、补偿和返回错误 |
| Graph Integration Test | 完整路径、暂停恢复、并行合并、失败降级 |
| End-to-End Eval | 最终业务结果、人工基线、安全、延迟和成本 |

### 14.2 必备测试案例

- **正常案例：**数据完整、工具正常、业务结果正确。
- **信息缺失：**系统能追问并继续，而不是编造。
- **模型错误：**结构化校验或规则能够拦截。
- **工具超时：**重试、恢复和幂等符合预期。
- **审批拒绝：**不会继续执行高风险工具。
- **Prompt Injection：**检索内容不能更改权限和系统规则。
- **版本迁移：**旧 checkpoint 能继续、回放或安全终止。

### 14.3 结果与轨迹同时评估

结果正确不代表过程安全；过程看起来合理也不代表业务事实正确。评测需要同时检查：

- 任务是否真正完成；
- 事实是否有正确来源；
- 路由和工具是否必要且正确；
- 是否发生越权、重复或多余副作用；
- 人工接管、延迟、Token 和成本是否可接受。

## 十五、Observability 与运营

每次运行至少应关联 `run_id`，并记录节点开始/结束、State diff、模型和 Prompt 版本、Context 引用、工具参数摘要、错误分类、Token、费用和延迟。

### 15.1 核心指标

- 端到端任务成功率与业务结果改善；
- 各节点、各路由和各工具成功率；
- 事实错误率、规则拦截率和越权率；
- 人工接管率、审批拒绝率和恢复成功率；
- P50/P95 延迟、模型调用数、Token 与单任务成本；
- 循环超限、重复工具调用和无进展运行比例。

Trace 用于解释“发生了什么”，评测集用于判断“是否正确”。二者必须同时存在。

## 十六、安全与治理

- **身份贯穿：**入口身份、Graph State、工具调用和审计使用一致主体。
- **最小权限：**工具权限按节点和任务动态授予，不能因为模型请求就扩大。
- **数据边界：**租户、部门、地域和敏感等级在检索与工具层强制过滤。
- **数据与指令分离：**外部文档和工具结果不能成为高优先级指令。
- **高风险审批：**审批界面展示动作、参数、证据、影响范围和回滚方式。
- **可终止：**提供运行取消、队列暂停、工具禁用和全局 kill switch。
- **保留策略：**明确 State、Trace、Prompt、输入输出和 Memory 的保存与删除周期。

## 十七、版本、迁移与回滚

Agent Graph 的行为由多个版本共同决定：

```text
Run Behavior = Graph Version
             + State Schema Version
             + Node Code Version
             + Prompt Version
             + Model Version
             + Tool / Policy Version
             + Retrieved Knowledge Version
```

### 17.1 变更风险

| 变更 | 主要风险 |
| --- | --- |
| 新增节点或边 | 旧任务下一执行位置与新结构不一致 |
| 删除或重命名节点 | 暂停中的任务无法恢复 |
| 修改 State 字段 | 旧 checkpoint 无法反序列化或语义变化 |
| 更换模型或 Prompt | 路由、输出结构和质量分布变化 |
| 修改工具 | 参数、权限、副作用和错误类型变化 |

发布前应运行固定回放集和迁移测试；高风险 Graph 采用影子模式、版本化流量和可回滚发布。长任务应固定关键组件版本，避免运行中途行为漂移。

## 十八、贯穿案例：把权限申请图工程化

### 18.1 最小 Graph

```text
receive
  → extract_request
  → check_missing ──缺失──→ ask_user ──→ check_missing
  → retrieve_policy
  → propose_access
  → deterministic_risk_check
       ├─ denied → explain_and_end
       ├─ normal → manager_approval
       └─ high → security_approval
  → grant_access
  → verify_actual_access
       ├─ success → notify_and_end
       └─ failed → retry_or_manual
```

这张图组装成 LangGraph 就是下面这段（节点函数的实现见第二十三章实战篇）：

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

builder = StateGraph(AccessRequestState)

# 注册节点（每个都是 (state)->dict 的函数）
for name, fn in {
    "extract_request": extract_request,
    "check_missing": check_missing,
    "ask_user": ask_user,
    "retrieve_policy": retrieve_policy,
    "propose_access": propose_access,
    "risk_check": deterministic_risk_check,
    "manager_approval": manager_approval,
    "security_approval": security_approval,
    "explain_and_end": explain_and_end,
    "grant_access": grant_access,
    "verify_access": verify_actual_access,
    "notify_and_end": notify_and_end,
    "retry_or_manual": retry_or_manual,
}.items():
    builder.add_node(name, fn)

builder.add_edge(START, "extract_request")
builder.add_conditional_edges(
    "extract_request",
    lambda s: "error" if s.get("errors") else "ok",
    {"error": "retry_or_manual", "ok": "check_missing"},
)

# 缺信息则追问，补齐后回到 check_missing 复查（循环边）
builder.add_conditional_edges(
    "check_missing",
    lambda s: "ask" if s["missing_fields"] else "ok",
    {"ask": "ask_user", "ok": "retrieve_policy"},
)
builder.add_edge("ask_user", "check_missing")
builder.add_edge("retrieve_policy", "propose_access")
builder.add_edge("propose_access", "risk_check")

# 风险分级：确定性路由（见 7.3）
builder.add_conditional_edges(
    "risk_check",
    lambda s: s["risk"]["level"],
    {"denied": "explain_and_end", "normal": "manager_approval", "high": "security_approval"},
)
for approval_node in ("manager_approval", "security_approval"):
    builder.add_conditional_edges(
        approval_node,
        lambda s: "approved" if s["approval_status"] == "approved" else "denied",
        {"approved": "grant_access", "denied": "explain_and_end"},
    )
builder.add_edge("grant_access", "verify_access")

# 验证：查 IAM 真相后决定收尾还是人工
builder.add_conditional_edges(
    "verify_access",
    lambda s: "ok" if s["execution"].get("verified") else "fail",
    {"ok": "notify_and_end", "fail": "retry_or_manual"},
)
builder.add_edge("notify_and_end", END)
builder.add_edge("explain_and_end", END)
builder.add_edge("retry_or_manual", END)  # 记录需人工处理；实际转交由调用方承担

app = builder.compile(checkpointer=MemorySaver())   # 生产换持久化 checkpointer
```

### 18.2 工程化设计

| 工程问题 | 设计答案 |
| --- | --- |
| 业务成功 | IAM 中实际权限与已批准方案一致，并有审批和审计记录 |
| 模型职责 | 抽取自然语言请求、归纳政策、生成最小权限候选方案 |
| 程序职责 | 身份、项目归属、互斥权限、期限、风险和最终权限比较 |
| 高风险动作 | 授权工具仅在审批状态有效时启用 |
| 恢复点 | 追问、审批和授权后分别 checkpoint |
| 幂等键 | run_id + grant_access + requester_id + role_id |
| 最终验证 | 重新查询 IAM，而不是相信授权 API 的 success 返回 |
| 主要评测 | 正确角色率、越权率、重复授权率、恢复成功率和处理时长 |

### 18.3 三条必须通过的轨迹

1. **正常：**标准角色 → 经理审批 → 授权 → 验证一致。
2. **失败恢复：**授权成功后服务崩溃 → 恢复先查询 IAM → 不重复授权。
3. **权限边界：**请求管理员权限或文档包含注入指令 → 进入安全审批或拒绝。

## 十九、常见失败模式

| 失败模式 | 根因 | 改进方向 |
| --- | --- | --- |
| 一张巨型图 | 把所有业务、Prompt 和异常集中在同一 Graph | 按业务边界拆子图，保持节点责任稳定 |
| 一切交给模型路由 | 把确定性状态和规则误当作语义判断 | 规则优先，模型只处理无法硬编码的分类 |
| State 变成数据垃圾场 | 保存全部历史、文档和工具输出 | 保存事实与引用，每个节点最小读写 |
| 有 checkpoint 却重复执行 | 外部副作用没有幂等和执行后验证 | 幂等键、业务操作记录、查询后重试 |
| Trace 很完整但任务仍失败 | 只有可观测性，没有 Ground Truth 和业务评测 | 建立真实评测集与最终业务状态校验 |
| 低代码图无法维护 | 节点过多、缺少代码审查和版本契约 | 关键逻辑代码化，图与 State 纳入版本控制 |
| 多 Agent 增加混乱 | 没有真正的权限或上下文隔离需求 | 回到单 Agent + 显式 Graph，按必要性拆分 |

## 二十、框架如何映射到工程能力

框架选型应在架构和工程要求明确之后进行：

| 方案 | 适合关注点 | 仍需自行建设 |
| --- | --- | --- |
| LangGraph | StateGraph、循环、持久化、interrupt 和复杂 Agent 工作流 | 业务权限、工具治理、评测集、应用与运维体系 |
| Microsoft Agent Framework Workflows | Executors、Edges、事件流和 .NET/Python 企业集成 | 具体业务控制、安全策略和生产运营 |
| OpenAI Agents SDK | Agent Loop、工具、handoff、guardrails、context 和 tracing | 复杂业务 Graph、持久化业务状态和系统集成 |
| Dify / Coze Studio / Flowise | 可视化 PoC、业务与研发协作、快速连接模型和工具 | 复杂状态迁移、深度定制、严格版本与大规模治理 |
| n8n / BPM 平台 | 确定性跨系统自动化，在节点中嵌入少量模型判断 | 开放式 Agent Loop、复杂模型 Context 与深度评测 |

不存在“最先进框架”的统一答案。选择取决于语言、部署环境、状态复杂度、云平台、工具来源、权限要求、可视化需求和团队维护能力。

### 20.1 按约束选型：决策判据表

不要问"哪个框架最好"，要问"我的约束把我逼到哪个方案"。从上往下走，第一个硬约束通常就决定了大方向：

| 你的硬约束 | 倾向方案 | 原因 |
|---|---|---|
| 主力语言是 **.NET / 企业微软栈** | Microsoft Agent Framework | 原生 .NET 集成，其余方案 Python 优先 |
| 需要**复杂状态 + 循环 + 持久化恢复 + 人工中断** | LangGraph | 这几项是它的原生能力，自建成本最高的部分它都给了 |
| 只是 **Agent Loop + 工具 + handoff**，状态不复杂 | OpenAI Agents SDK | 更轻，不必背 StateGraph 的复杂度 |
| 要**业务/产品同学也能改流程**、快速 PoC | Dify / Coze / Flowise | 可视化协作，但复杂迁移和治理要另想办法 |
| 本质是**确定性跨系统自动化**，模型只是点缀 | n8n / BPM 平台 | 别为了少量模型判断上重型 Agent 框架 |
| 一次模型调用就够、无多阶段状态 | **不用任何 Graph 框架** | 直接调 SDK，Graph 是负债不是资产 |

### 20.2 选型前必须先答的问题

框架只解决"控制结构"，下面这些**每个框架都要你自建**，选型前先确认团队有能力补：

- **状态存哪**：进程内内存只够 Demo；生产要 Postgres/持久化 checkpointer。
- **工具治理**：权限、审计、幂等——框架给接口，业务规则要自己写。
- **评测集**：没有哪个框架自带你的业务 Ground Truth。
- **运维**：kill switch、预算熔断、影子发布、版本回滚。

**判据一句话**：先用第四~十七章明确工程要求，再回到这张表选框架——反过来（先选框架再想需求）是最常见的返工来源。

## 二十一、上线前工程检查清单

### 设计

- 业务成功标准和权威事实来源明确；
- Graph 只包含必要的模型判断点；
- 每个节点、边、循环和退出条件可解释；
- Node Contract 明确 Worker 可自行收集的信息、允许工具和缺失信息返回协议；
- Worker 本地问答有交互 ID、Session 路由和恢复契约；统一对话框按事件类型展示；
- 跨 Worker 信息依赖通过显式 Edge / 子图协调，不存在隐藏横向调用；
- State、Context、RAG、Memory 和业务数据库已分离。

### 可靠性

- 节点超时、重试、降级和人工接管路径齐全；
- `needs_information` 的用户、工具、Worker、权限和 State 回流路径均经过测试；
- 同时有多个 Worker 待答、重复回复、过期回复和取消后的回传路径经过测试；
- Worker 暂停恢复保留 continuation、幂等键和外部执行凭证，不重复副作用；
- 写工具具备幂等、补偿和执行后验证；
- checkpoint、暂停、恢复、取消和并行合并经过测试；
- 运行时具备预算、最大步数和 kill switch。

### 安全

- 身份、租户、数据范围和工具权限贯穿全链路；
- 高风险动作由规则和人工审批控制；
- Prompt Injection、越权和敏感数据外泄用例已测试；
- 日志、State 和 Memory 有保留与删除策略。

### 评测与运营

- 正常、失败、边界、恶意和版本迁移测试集齐全；
- 同时评估最终结果、执行轨迹和真实副作用；
- 关键组件版本可追踪、可回放和可回滚；
- 告警、排障、人工接管和积压处理责任人明确。

## 二十二、理解检查

1. 为什么 Agent Graph Engineering 的起点不是选择框架或 Agent 数量？
2. State 与 Context 分别应该保存什么？为什么不能把完整 State 直接发给模型？
3. 什么时候应该使用 Loop，什么时候必须使用确定性 Edge？
4. 为什么 checkpoint 无法单独解决重复写入问题？
5. 一个 Node Contract 至少应包含哪些字段？
6. 如何证明一个 Graph 不仅回答正确，而且没有越权或重复副作用？
7. 修改节点、State 或 Prompt 后，运行中的旧任务应该如何处理？
8. Worker 缺少信息时，哪些情况应自行收集，哪些必须返回 Graph？为什么默认不允许 Worker 横向调用其他 Worker？
9. 多个 Worker Session 如何映射到同一对话框？局部 Human-in-the-loop 的答案为什么应直接回到原 Worker？恢复时哪些代码可能重跑？

> **掌握判断：**如果你能够从一个业务目标出发，设计最小 Graph 和 State，写出节点与工具契约，说明 Loop、Context、Harness 和传统系统的责任，设计正常、失败和权限边界测试，并解释如何恢复和迁移，就已经掌握 Agent Graph Engineering 的核心。

## 二十三、组装示例：权限申请图的实现骨架

这一章把前面的契约与节点串成权限申请图，展示组装方式。它是待补依赖的设计骨架；缺少模型、IAM、政策检索适配器及完整测试环境，不能直接运行，也不能据此判断已经具备上线条件。

> **示例状态：待补依赖，未整体验证。**需要实现 `call_llm`、`call_llm_propose`、`iam_client`、`policy_search`、`execution_log` 等依赖，把 `execution` 加入 State，并固定 LangGraph/Pydantic 版本后再运行。本文的测试片段是验收意图示例。可直接运行的入门练习见[只读诊断案例](<../质量与实践/examples/read_only_diagnosis/README.md>)。

### 23.1 落地五步

```text
① 定 State（接口）   → 23.2
② 写节点（责任）     → 23.3
③ 连边（控制流）     → 23.4，即第 18.1 的组装代码
④ 加恢复与审批       → 23.5（checkpointer + interrupt）
⑤ 写三条测试轨迹     → 23.6
```

### 23.2 State：直接复用第五章

State 就用 5.2 的 `AccessRequestState`，这里补上执行子状态字段：

```python
class ExecutionState(TypedDict, total=False):
    status: str           # granted | already_done | verified_existing | failed
    op_id: str
    verified: bool

# AccessRequestState 中：execution: ExecutionState
```

### 23.3 节点实现（每个节点只干一件事）

```python
# —— 追问缺失信息：用 interrupt 暂停等人工补齐 ——
from langgraph.types import interrupt

REQUIRED = ["requester_id", "project_id", "requested_roles"]

def check_missing(state):
    missing = [f for f in REQUIRED if not state["request"].get(f)]
    return {"missing_fields": missing}

def ask_user(state):
    # 暂停图，把缺失字段抛给人；恢复时拿到用户补的值
    answer = interrupt({"need": state["missing_fields"]})
    return {"request": {**state["request"], **answer}}

# —— 检索政策（只读） ——
def retrieve_policy(state):
    refs = policy_search(state["request"]["project_id"])   # 返回 Artifact ID，不塞全文
    return {"evidence_refs": refs}

# —— 模型生成最小权限候选（无副作用） ——
def propose_access(state):
    roles = call_llm_propose(state["request"], state["evidence_refs"])
    return {"proposed_roles": roles}

# —— 确定性风险分级（见 6.1.1，纯程序） ——
# deterministic_risk_check 同 6.1.1

# —— 审批：两级都用 interrupt 暂停 ——
def manager_approval(state):
    decision = interrupt({"approve": state["proposed_roles"], "level": "manager"})
    return {"approval_status": "approved" if decision == "yes" else "denied"}

def security_approval(state):
    decision = interrupt({"approve": state["proposed_roles"], "level": "security"})
    return {"approval_status": "approved" if decision == "yes" else "denied"}

# —— 高风险写入：带幂等键（见 12.2.1） ——
# grant_access 同 12.2.1，但先检查 approval_status
def grant_access(state):
    if state["approval_status"] != "approved":
        return {"execution": {"status": "failed", "verified": False}}
    return _grant_with_idempotency(state)   # 12.2.1 的实现

# —— 执行后验证：查 IAM 真相，不信 API 的 success ——
def verify_actual_access(state):
    ok = iam_client.has_roles(state["request"]["requester_id"], state["proposed_roles"])
    return {"execution": {**state["execution"], "verified": ok}}

def notify_and_end(state):
    notify(state["request"]["requester_id"], "granted")
    return {}

def explain_and_end(state):
    return {}

def retry_or_manual(state):
    return {"errors": [{"node": "handoff", "detail": "当前分支无法自动完成，需人工核对已有错误与执行结果"}]}
```

### 23.4 连边

组装代码见 **18.1**（`add_conditional_edges` + `compile(checkpointer=...)`），此处不重复。

### 23.5 恢复与审批：跑一次暂停—恢复

`interrupt()` 配合 checkpointer 保存暂停状态。第 18.1 节使用 `MemorySaver`，下面只演示同一进程、同一个 checkpointer 实例内的恢复。要在进程退出后继续，必须先换成持久化 checkpointer，并保证恢复端访问相同存储和兼容的图定义：

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": run_id}}

# 第一次跑：在 manager_approval 处暂停，控制权交还调用方
result = app.invoke(initial_state, config=config)
# result 中含中断信息；MemorySaver 只保存在内存中，进程重启会丢失

# 人给出审批后，用同一个 thread_id 恢复
result = app.invoke(Command(resume="yes"), config=config)
```

**恢复条件：**内存 checkpointer 支持进程存活期间继续调用；持久化 checkpointer 才能支持跨进程恢复。暂停可以释放当前执行调用，但内存状态仍依赖进程存活。恢复时节点还可能重新执行，副作用仍要按第十二章处理。[官方持久化说明](https://docs.langchain.com/oss/python/langgraph/persistence)

### 23.6 三条验收轨迹（待补测试依赖）

```python
def make_state(**over):
    base = {
        "schema_version": "1", "graph_version": "1", "run_id": "t1",
        "request": {"requester_id": "u1", "project_id": "p1",
                    "requested_roles": ["reader"], "justification": "..."},
        "missing_fields": [], "proposed_roles": None, "risk": None,
        "approval_status": "pending", "evidence_refs": [],
        "retry_count": {}, "errors": [], "execution": {},
    }
    base.update(over)
    return base

# ① 正常：标准角色 → 经理审批 → 授权 → 验证一致
def test_happy_path(monkeypatch):
    cfg = {"configurable": {"thread_id": "happy"}}
    app.invoke(make_state(), cfg)             # 停在 manager_approval
    out = app.invoke(Command(resume="yes"), cfg)
    assert out["execution"]["verified"] is True
    assert out["approval_status"] == "approved"

# ② 失败恢复：授权成功后崩溃 → 恢复先查 IAM → 不重复授权
def test_recovery_no_double_grant(monkeypatch):
    # 预置：IAM 里已经有权限（模拟崩溃前已写入）
    iam_client.seed("u1", ["reader"])
    calls = []
    monkeypatch.setattr(iam_client, "grant", lambda *a, **k: calls.append(1))
    out = grant_access(make_state(approval_status="approved",
                                  proposed_roles=["reader"]))
    assert out["execution"]["status"] == "verified_existing"
    assert calls == []                        # 关键：一次真实授权都没发生

# ③ 权限边界：请求管理员权限 → 必须走 security_approval，且未批不得授权
def test_high_risk_requires_security():
    s = make_state(proposed_roles=["admin"])
    s.update(deterministic_risk_check(s))
    assert s["risk"]["level"] == "high"        # 分级正确
    # 未批准直接调 grant 必须拒绝
    out = grant_access(make_state(approval_status="pending",
                                  proposed_roles=["admin"]))
    assert out["execution"]["status"] == "failed"
```

这三条对应第十八章的三条轨迹，覆盖了**正常结果、恢复幂等、权限边界**三类最关键的失败面。它们只是起步验收用例；还需覆盖审批拒绝、Schema 失败、外部系统超时、并发和真实持久化恢复，并按业务风险补全上线验证。

## 主要官方资料

- [LangGraph Overview](https://langchain-ai.github.io/langgraph/index.html)
- [LangGraph Graph API Overview](https://langchain-ai.github.io/langgraph/how-tos/configuration/)
- [LangGraph Interrupts](https://langchain-ai.github.io/langgraph/concepts/breakpoints/)
- [Microsoft Agent Framework Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)
- [OpenAI Agents SDK：Running agents](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK：Context management](https://openai.github.io/openai-agents-python/context/)
- [OpenAI Agents SDK：Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI：Harness engineering](https://openai.com/index/harness-engineering/)

*说明：框架功能、API 和托管能力变化较快，正式选型与落地前应重新核对官方文档。*
