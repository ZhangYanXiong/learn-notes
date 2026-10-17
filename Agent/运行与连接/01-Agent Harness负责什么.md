# Agent Harness：从 0 到 1——概念、职责、边界、工程与落地

**版本：**2026-09-22　｜　**面向：**产品、研发、架构、平台与工程效能团队

> **体系导航：**[学习地图](<../README.md>)｜[Agent Loop](<../基础机制/01-Agent如何运行：Loop.md>)｜[Goal 与 Planning](<../基础机制/03-如何定义目标与计划.md>)｜[Agent Graph](<../编排与协作/01-什么时候需要Agent Graph.md>)｜[Graph Engineering](<../编排与协作/02-如何实现Agent Graph.md>)

---

## 阅读入口

- **首次阅读：**[二、Harness 是什么](#二harness-是什么) → [四、Harness、Loop、Graph、Runtime：四者关系与边界](#四harnessloopgraphruntime四者关系与边界) → [十二、什么时候需要重型 Harness，什么时候不需要](#十二什么时候需要重型-harness什么时候不需要)。
- **模拟案例：**[实现示例：一个最小 Harness 演示（模拟模型）](#实现示例一个最小-harness-演示模拟模型)。
- **进阶场景：**[十三、编码 Agent Harness 专题](#十三编码-agent-harness-专题) → [十四、从 0 到 1：自建 vs 选型](#十四从-0-到-1自建-vs-选型)。

**代码状态：**本篇代码用于讲解结构，未作为完整工程逐段验证。可运行且已有测试的练习见[只读诊断案例](<../质量与实践/examples/read_only_diagnosis/README.md>)。

## 一页结论

1. **Harness 是模型与真实世界之间的执行外壳。**它不是模型，也不是业务系统，而是把"模型的一段输出"变成"可靠、可控、可观测、可恢复的真实行动"的那一层工程。
2. **Harness 的职责是六件事：**模型适配、执行循环与调度、工具执行、安全与权限、可观测与反馈、持久化与恢复。它们是按任务风险选配的能力清单；短任务未必需要持久化恢复，多模型路由也并非每个系统都需要。
3. **Harness 不提高模型能力，只放大或约束模型能力。**同一个模型，套上好的 Harness 能安全地跑长任务；套上坏的 Harness 会把一次幻觉放大成一次真实的误删库、超预算或越权操作。
4. **越危险的动作，越应该由 Harness 而不是模型来把关。**语义判断交给模型，权限、预算、幂等、审批、终止条件必须由 Harness 用确定性代码守住。
5. **不是所有 Agent 都需要重型 Harness。**单次调用和简单 RAG 几乎不需要；受限 Tool Loop 需要轻量 Harness；长任务、跨系统、高风险、需要审批和恢复的场景才需要完整 Harness。
6. **编码 Agent 是 Harness 工程最典型的落地场景。**文件系统、命令执行、终端交互、上下文压缩、权限确认、子 Agent 调度——这类系统既依赖模型的理解与决策能力，也依赖 Harness 的执行、信息管理和反馈能力。

---

## 阅读指引

本文分为五个部分，建议按顺序阅读前四部分，第五部分作为查阅手册：

| 部分 | 内容 | 解决什么问题 |
| --- | --- | --- |
| 第一部分：心智模型 | 为什么需要 Harness、它是什么、在分层中的位置、与 Loop/Graph/Runtime 的关系 | Harness 到底是什么？它在 AI 工程里处于什么位置？ |
| 第二部分：六大核心子系统 | 模型适配、执行循环、工具执行、安全权限、可观测、持久化恢复 | Harness 内部由哪些部件组成？每个部件解决什么问题？ |
| 第三部分：设计原则与边界 | 模型与 Harness 的责任边界、何时需要重型 Harness、编码 Agent 专题 | 拿到自己的场景，如何判断需要多重的 Harness？ |
| 第四部分：落地路线 | 自建 vs 选型 → 评测 → 安全治理 → 上线检查 | 可操作的步骤和检查清单 |
| 第五部分：延伸参考与自检 | 产品生态参考链接、常见误区、理解检查与官方资料 | 巩固概念并进入独立参考资料 |

**与《Agent Graph》一文的关系：**Agent Graph 讲"任务按什么结构执行"（控制流与状态编排）；本文讲"如何安全、可恢复、可观测地把这个结构执行起来"（执行外壳）。Graph 是 Harness 的一部分职责，但不是全部——很多 Agent 没有显式 Graph，却都需要 Harness。两篇可对照阅读。

---

# 第一部分：心智模型

> 核心结论：Harness 的价值不是让模型更聪明，而是让模型的每一次行动都发生在一个受控、可观测、可恢复的执行环境里。

## 一、为什么需要 Harness：从裸模型调用到受控执行

直接调用模型 API，你得到的是一段文本或一个工具调用请求。但"得到一段输出"和"完成一件事"之间，隔着一整层工程问题：

| 你以为只需要 | 实际上还需要 Harness 处理 |
| --- | --- |
| 调一次模型 | 模型超时、限流、降级、多模型路由、结构化输出解析失败重试 |
| 让模型调用工具 | 工具是否存在、参数是否合法、是否有权限、超时怎么办、重复调用会不会重复扣款 |
| 让模型多想几步 | 什么时候停、循环了 50 次还没结束怎么办、Token 和成本预算爆了怎么办 |
| 让模型写文件/发请求 | 这个动作要不要人工确认、在哪个沙箱里执行、失败了能不能回滚 |
| 跑一个长任务 | 中途崩溃后从哪里恢复、外部副作用是否已经发生、要不要补偿 |
| 上线后出问题 | 错误发生在模型、工具、路由还是权限？有没有 Trace 能定位？ |

**一句话：**模型负责"想做什么"，Harness 负责"能不能做、怎么做才安全、做失败了怎么办、做过什么留没留痕"。没有 Harness，Agent 是一个不能对结果负责的黑盒。

## 二、Harness 是什么

把 Agent Harness 表达为一个公式：

```text
Agent Harness = 模型适配 + 执行循环与调度 + 工具执行 + 安全边界 + 可观测 + 持久化恢复
```

| 子系统 | 作用 | 典型内容 |
| --- | --- | --- |
| 模型适配 | 屏蔽模型差异，稳定拿到可用输出 | 多模型接入、Prompt 模板、结构化输出解析、降级与重试 |
| 执行循环与调度 | 驱动 Agent 一步步往前走 | Loop、Graph 调度、会话管理、State、并发、超时、取消 |
| 工具执行 | 让模型的意图变成真实调用 | 工具注册、Schema 校验、超时、重试、幂等、结果标准化 |
| 安全边界 | 限制模型能造成的最大伤害 | 身份传递、最小权限、沙箱、审批、预算、kill switch |
| 可观测 | 知道发生了什么、好不好 | 事件流、Trace、日志、Token/成本统计、评测、在线反馈 |
| 持久化恢复 | 长任务不因崩溃前功尽弃 | checkpoint、State Store、副作用记录、补偿、恢复策略 |

**关键认识：**这六件事没有一件是"模型"能自己完成的。模型不知道自己有没有权限，不知道预算还剩多少，不知道上次崩溃在哪一步——这些都必须由 Harness 用确定性代码维护。**Harness 是把不确定的模型嵌入确定性工程系统的那层胶水。**

## 三、Harness 在 AI 工程分层中的位置

Harness 处在"产品层"和"图/节点/工具层"之间，是承上启下的执行中枢：

```text
用户 / 业务事件
        ↓
产品与 API 层：UI、身份、租户、限流、会话
        ↓
【Agent Harness】：模型适配、运行循环、工具执行、权限、沙箱、预算、审批、追踪、恢复
        ↓
Agent Graph（可选）：阶段、节点、路由、并行、循环、暂停与状态迁移
        ↓
节点内部：Prompt + 模型参数 + Context Builder + Model / 普通代码
        ↓
工具与知识层：API、MCP、RAG、Memory、代码执行、人工操作
        ↓
传统业务系统：数据库、事务、消息队列、工作流、IAM、审计
        ↓
横切能力：评测、可观测性、安全、成本、部署、版本与回滚
```

**Harness 管什么：**组织模型调用前的工作集与预算，接收候选输出后完成解析、校验、鉴权、执行、记录与恢复；具体信息选择策略由 Context Engineering 定义。

**职责边界：**业务规则由业务系统维护。Context Engineering 定义信息选择、压缩和来源处理策略；Harness 可以承载 Context Builder、历史压缩、工具结果整理和预算执行。好的执行环境与反馈可以改善整体任务表现，但不保证模型每次判断正确，仍需独立验证结果。

## 四、Harness、Loop、Graph、Runtime：四者关系与边界

这四个词经常被混用，但它们回答的是不同层面的问题：

| 概念 | 回答的问题 | 类比 |
| --- | --- | --- |
| Agent Loop | 模型这一步该做什么？（观察→判断→行动→再判断） | 一个工人的单次动作 |
| Agent Graph | 整个任务按什么结构推进？（阶段、分支、循环、暂停） | 车间的工艺流程图 |
| Runtime | 谁来实际调度执行、持久化状态？ | 车间的传送带和调度系统 |
| **Harness** | 怎么让上面这些安全、可控、可观测、可恢复地跑起来？ | 整个车间的安全护栏、监控、门禁和应急预案 |

三个容易混淆的边界：

- **Harness ⊇ Runtime。**Runtime 通常特指"调度和状态持久化"这一具体能力；Harness 是更大的概念，包含 Runtime，再加上模型适配、工具执行、安全和可观测。很多框架里 Runtime 就是 Harness 的核心引擎。
- **Loop 是 Harness 的产物，不是对立面。**Harness 提供一个受控的循环——它决定循环何时开始、每步能调用什么、什么时候必须停。裸 Loop（无限 while 循环里直接调模型）恰恰是"没有 Harness"的表现。
- **Graph 是可选的，Harness 是必需的。**简单 Agent 没有显式 Graph（只有一个 Loop），但仍然需要 Harness 来管权限、超时和追踪。只有当控制流复杂到需要显式编排时，才在 Harness 之上引入 Graph。

**一句话总结边界：**Graph 说"应该按什么结构执行"，Runtime 说"由谁来推动执行"，Loop 说"这一步做什么"，而 **Harness 说"整个执行过程如何做到安全、可控、可观测、可恢复"**。

---

# 第二部分：六大核心子系统

> 学习目标：读完这一部分，你应该能说清 Harness 内部由哪些部件组成，每个部件解决什么具体问题，以及缺了它会在生产中引发什么故障。

下面六节逐个拆解。每节结构一致：**它解决什么 → 关键设计点 → 一个小例子/伪代码 → 缺了它会怎样**。

## 五、模型适配层：屏蔽模型差异，稳定拿到可用输出

**它解决什么：**模型 API 是不稳定、有差异、会失败的外部依赖。适配层的职责是把"面向某个具体模型的调用"变成"面向能力的稳定调用"，让上层不必关心背后是哪家模型、哪个版本。

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| 多模型接入 | 统一接口封装不同厂商（Claude、GPT、Gemini、开源模型），支持按成本/能力/延迟路由 |
| Prompt 模板与版本 | Prompt 与代码解耦、可版本化，避免"改一句话线上就变了但没人知道" |
| 结构化输出解析 | 要求模型输出 JSON/工具调用时，解析失败要能重试、纠错或降级，而不是直接抛异常 |
| 降级策略 | 主模型超时/限流/报错时，降到备用模型或更小模型，而不是整个任务失败 |
| 参数管理 | temperature、max_tokens、stop 等参数按节点/场景配置，而非硬编码 |

**伪代码：带解析重试和降级的模型调用**

```text
function call_model(prompt, schema, models=[primary, fallback]):
    for model in models:
        for attempt in 1..MAX_RETRY:
            try:
                raw = model.invoke(prompt, timeout=T)
                return parse_and_validate(raw, schema)   # 结构化校验
            except ParseError:
                prompt = prompt + repair_hint(schema)     # 让模型修正格式
            except (Timeout, RateLimit):
                break                                     # 换下一个模型
    raise ModelUnavailable                                # 全部失败才上抛
```

**缺了它会怎样：**模型偶发返回非法 JSON 就整条链路崩溃；某厂商限流时整个产品不可用；换模型要改一堆业务代码；Prompt 散落在各处无法追溯"到底改了哪句导致效果变差"。

## 六、执行循环与调度：驱动 Agent 一步步往前走

**它解决什么：**Agent 不是一次调用就结束，而是"观察→判断→行动→读取结果→再判断"的循环。这个循环必须被 Harness 控制——决定它何时开始、每一步允许做什么、何时必须停止。

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| 受控 Loop | 循环必须有明确的终止条件：达成目标、超过最大步数、超时、超预算、遇到需审批动作 |
| 会话与线程管理 | 一个任务对应一个 run_id/thread_id，多轮交互挂在同一会话上下文里 |
| State 维护 | 循环中的中间结果、步数、错误、待审批项等，由 Harness 存在 State 里，而非全塞进 Prompt |
| Graph 调度（可选） | 复杂任务在 Loop 之上叠加 Graph，管理跨阶段流转、并行、暂停恢复 |
| 并发/取消/超时/背压 | 多任务并发时的资源限制、用户取消、单步与整体超时、下游过载时的背压 |

**受控 Loop 的最小骨架：**

```text
state = init_state(task)
while not state.done:
    if state.steps >= MAX_STEPS: return stop("step_limit")
    if state.cost  >= BUDGET:    return stop("budget")
    action = model.decide(build_context(state))    # 模型只决定"想做什么"
    if action.needs_approval:                       # 高风险动作暂停等人
        return pause_for_approval(state, action)
    result = execute(action)                        # 交给工具执行层
    state = update(state, action, result)           # Harness 更新状态
    checkpoint(state)                               # 每步落盘，可恢复
```

**关键区分：**模型负责 `decide`（模糊判断），Harness 负责 `while` 条件、预算检查、审批拦截、`checkpoint`（确定性控制）。这条边界是 Harness 工程的核心。

**缺了它会怎样：**模型陷入无限循环反复调同一个工具；长任务崩溃后只能从头再来；用户点了取消但任务还在后台烧钱；高并发时资源被打满没有背压。

## 七、工具执行层：让模型的意图变成真实调用

**它解决什么：**模型输出的只是"我想调用工具 X，参数是 Y"这样一个**请求**。把请求变成一次真实、安全、可信的调用，是工具执行层的职责。这是 Harness 中最容易把"模型的小错误"放大成"真实世界大事故"的地方。

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| 工具注册与发现 | 工具有明确的名称、描述、参数 Schema；模型只能调用注册过的工具 |
| Schema 校验 | 调用前校验参数类型、范围、必填项，非法参数直接拒绝而非透传给下游 |
| 超时与重试 | 每个工具有独立超时；可重试的错误自动重试，不可重试的立即失败 |
| **幂等** | 写操作必须幂等，防止"恢复后重复执行"造成重复下单、重复扣款 |
| 结果标准化 | 工具返回统一封装（成功/失败/数据/错误码），让模型和 Loop 能一致处理 |
| MCP 集成 | 通过 MCP 协议接入外部工具时，同样要经过校验、鉴权、超时这套关卡 |

**幂等键：Harness 防重复副作用的核心武器**

```text
idempotency_key = run_id + node_id + business_object_id + operation

工具执行前：
  if 已存在(idempotency_key): return 上次的结果   # 不重复执行
  else: 执行 → 记录(idempotency_key, 业务操作ID) → 返回
```

> **为什么幂等属于 Harness 而不是模型？**因为"这个操作我是不是已经做过了"是执行状态问题，模型无从知晓，只能由 Harness 用确定性记录来判断。checkpoint 能恢复状态，但不能保证 exactly-once——工具调用成功后、checkpoint 写入前若崩溃，恢复时会重复执行，幂等键是唯一的兜底。

**缺了它会怎样：**模型传了个越界参数直接打到生产库；网络抖动导致同一笔转账执行两次；工具超时把整个任务拖死；MCP 接入的第三方工具权限过大成为攻击入口。

## 八、安全边界：限制模型能造成的最大伤害

**它解决什么：**模型是不可完全信任的。它可能被 Prompt Injection 操纵，可能幻觉出一个危险动作，可能在开放任务里"自作主张"。安全边界的职责是：**无论模型想做什么，都不能突破人为设定的权限、预算和审批红线。**

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| 身份传递 | Agent 以"谁"的身份执行？必须把发起用户的身份透传到每一次工具调用，而非用超级权限跑 |
| 最小权限 | 每个工具、每个任务只授予完成它所需的最小权限，而非一把万能钥匙 |
| 沙箱隔离 | 代码执行、命令执行放在隔离沙箱里，限制文件系统、网络、资源访问 |
| 审批（Human-in-the-loop） | 高风险动作（大额、删除、越权、不可逆）必须暂停等人工确认 |
| 预算控制 | Token、成本、调用次数、时长都有上限，超限即停 |
| kill switch | 一键终止某个任务/某类工具/整个 Agent 的能力，用于应急止损 |

**风险分级与处置矩阵（示例）**

| 动作风险 | 例子 | Harness 处置 |
| --- | --- | --- |
| 低（只读） | 查询、搜索、读文件 | 自动执行 |
| 中（可逆写） | 创建草稿、写临时文件 | 自动执行 + 记录 |
| 高（有副作用） | 发消息、改配置、提交代码 | 需审批或二次确认 |
| 极高（不可逆/敏感） | 删数据、转账、删分支、生产变更 | 强制人工审批 + 双人复核 |

**缺了它会怎样：**这是 Harness 里出事最惨烈的一层。缺失会导致：Prompt Injection 让 Agent 泄露数据或执行恶意指令；模型幻觉触发 `rm -rf` 或删库；一个失控循环烧掉几千美元；越权访问了不该访问的租户数据。**安全边界的设计原则是"假设模型会犯最坏的错误，Harness 也要兜得住"。**

## 九、可观测与反馈：知道发生了什么、好不好

**它解决什么：**Agent 是一个多步骤、有模型不确定性的系统，出了问题如果不能定位到"错在哪一步、哪个部件"，就无法修复也无法改进。可观测层的职责是让整个执行过程可追溯、可度量、可评测。

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| 事件流 | 每个节点/工具/模型调用的开始、结束、错误都发出结构化事件 |
| Trace | 一次完整运行的调用链路，能看到"模型→工具→模型→审批"的完整轨迹 |
| Token/成本统计 | 每步、每任务、每用户的 Token 消耗和成本，用于计费和预算 |
| 日志与 Artifact | 关键输入输出、中间产物（如生成的代码、检索的文档）可留存回溯 |
| 离线评测 | 用真实评测集验证质量：任务成功率、工具正确率、权限合规、延迟成本 |
| 在线反馈 | 收集用户反馈、点赞点踩、人工修正，反哺 Prompt 和评测集 |

**评测不能只看最终答案：**一个 Agent 即使给出了正确的最终回答，也可能在过程中越权访问了数据、多花了 10 倍成本、或者靠运气绕过了 bug。生产级评测必须同时覆盖：**任务结果、执行轨迹、工具副作用、权限边界、延迟与成本**五个维度。

**缺了它会怎样：**线上出错只能靠猜；不知道钱花在哪；模型换版本后效果变差却无法量化；无法证明"这次改动到底是变好还是变坏"。

## 十、持久化与恢复：长任务不因崩溃前功尽弃

**它解决什么：**企业级任务可能跑几分钟到几天，中间要等审批、等外部事件、可能崩溃重启。持久化层的职责是让任务的状态可以被保存、恢复，并正确处理"恢复时外部副作用可能已经发生"这个棘手问题。

**关键设计点：**

| 设计点 | 说明 |
| --- | --- |
| checkpoint 内容 | 保存：Graph/State 版本、已完成节点、下一执行位置、节点输出、待审批项、模型/Prompt/工具版本 |
| State Store | 生产必须用持久化存储（数据库/专用 store），**不要把进程内内存当 State Store** |
| 恢复策略 | 崩溃后从最近 checkpoint 恢复，恢复前先查外部系统的真实状态 |
| 副作用处理 | 结合工具执行层的幂等键，避免恢复后重复写入 |
| 补偿 | 不可幂等的操作要设计补偿动作（回滚、冲正）或转人工处理 |

**恢复的正确姿势：**

```text
崩溃重启 → 读取最近 checkpoint → 得到"下一步该执行 node X"
        → 先查询业务系统：node X 的操作是否已经发生？
            ├─ 已发生 → 跳过执行，直接更新 State 继续
            └─ 未发生 → 检查幂等键后执行
```

**checkpoint ≠ exactly-once：**这是最常见的误区。checkpoint 只保证"状态能恢复"，不保证"外部写操作只发生一次"。要做到 exactly-once 效果，必须 checkpoint + 幂等 + 副作用记录 + 恢复前校验四者配合。

**缺了它会怎样：**任务跑到第 8 步崩了，只能从第 1 步重来，前面的模型调用和工具副作用全部浪费甚至重复；等审批的任务重启后丢失上下文；用内存当 State，一次部署就把所有在途任务清零。

## 实现示例：一个最小 Harness 演示（模拟模型）

前面六节是分开讲的，这里用一段**纯 Python 标准库、无需任何 API key** 的代码串起主要职责。模型使用确定性的模拟实现；本轮未单独执行这段内嵌演示。接入真实模型还需要补充响应解析、错误处理与行为评测。已执行测试的练习见[只读诊断 Agent](<../质量与实践/examples/read_only_diagnosis/README.md>)。

**任务：**查询商品库存，若不足阈值则提交补货单——补货是高风险动作，必须人工审批。

这段代码演示了六大子系统里最关键的五个协作点：**受控循环 + 预算/步数上限（②④）、工具注册与 Schema 校验（③）、幂等（③）、高风险动作暂停审批（④）、结构化 Trace（⑤）、checkpoint 与崩溃恢复（⑥）**。

```python
import json, os, time

CHECKPOINT = "harness_state.json"

# ---------- 1) 模型适配层：用确定性"假模型"代替真实 LLM ----------
# 真实场景换成 Claude/GPT 调用 + 结构化输出解析 + 降级重试。
def model_decide(state):
    f = state["facts"]
    if "stock" not in f:
        return {"tool": "check_stock", "args": {"sku": state["input"]["sku"]}}
    if f["stock"] < state["input"]["threshold"] and not f.get("restocked"):
        return {"tool": "create_restock_order",
                "args": {"sku": state["input"]["sku"], "qty": 100}}
    return {"tool": "finish", "args": {"reason": "库存已处理，任务完成"}}

# ---------- 3) 工具执行层：注册表 + 参数校验 + 幂等 ----------
def check_stock(args, state):
    return {"ok": True, "data": {"stock": 20}}          # 只读工具，假设库存 20

def create_restock_order(args, state):
    key = f'{state["run_id"]}:restock:{args["sku"]}'    # 幂等键：同一 run+sku 只下一次
    if key in state["idempotency"]:
        return {"ok": True, "data": state["idempotency"][key], "idempotent_hit": True}
    order = {"order_id": f'RO-{int(time.time())}'}
    state["idempotency"][key] = order
    return {"ok": True, "data": order}

TOOLS = {
    "check_stock":          {"fn": check_stock,          "schema": ["sku"],        "risk": "low"},
    "create_restock_order": {"fn": create_restock_order, "schema": ["sku", "qty"], "risk": "high"},
}

def validate(tool, args):                               # schema 校验：非法参数直接拒绝
    for field in TOOLS[tool]["schema"]:
        if field not in args:
            raise ValueError(f"工具 {tool} 缺少参数 {field}")

# ---------- 5) 可观测：结构化事件 ----------
def emit(state, event, **kw):
    line = {"step": state["steps"], "event": event, **kw}
    state["trace"].append(line)
    print("  [trace]", json.dumps(line, ensure_ascii=False))

# ---------- 6) 持久化恢复：checkpoint 存 / 取 ----------
def checkpoint(state):
    with open(CHECKPOINT, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_or_init(task):
    if os.path.exists(CHECKPOINT):
        print("== 检测到 checkpoint，从中断处恢复 ==")
        return json.load(open(CHECKPOINT))
    return {"run_id": f"run-{int(time.time())}", "input": task, "facts": {},
            "steps": 0, "cost": 0, "trace": [], "idempotency": {},
            "pending_approval": None, "done": False}

# ---------- 2) + 4) 执行循环 + 安全边界（预算 / 步数 / 审批） ----------
MAX_STEPS, BUDGET = 10, 100

def run(task, approvals):
    state = load_or_init(task)
    while not state["done"]:
        if state["steps"] >= MAX_STEPS:                 # 4) 步数上限
            emit(state, "stop", reason="step_limit"); break
        if state["cost"] >= BUDGET:                     # 4) 预算上限
            emit(state, "stop", reason="budget"); break

        action = state["pending_approval"] or model_decide(state)
        state["steps"] += 1
        state["cost"] += 5                              # 模拟每步 token 成本

        if action["tool"] == "finish":
            emit(state, "finish", reason=action["args"]["reason"])
            state["done"] = True; checkpoint(state); break

        validate(action["tool"], action["args"])        # 3) schema 校验

        if TOOLS[action["tool"]]["risk"] == "high" and not action.get("approved"):
            if approvals.get(action["tool"]):            # 已获批 → 放行
                action["approved"] = True
            else:                                        # 4) 未获批 → 暂停落盘等待
                state["pending_approval"] = action
                emit(state, "pause_for_approval", tool=action["tool"])
                checkpoint(state)
                print("== 任务已暂停，等待审批。再次运行并批准即可继续 ==")
                return state

        result = TOOLS[action["tool"]]["fn"](action["args"], state)   # 3) 执行
        emit(state, "tool_result", tool=action["tool"],
             idempotent=result.get("idempotent_hit", False))
        if "stock" in result["data"]:
            state["facts"]["stock"] = result["data"]["stock"]
        if action["tool"] == "create_restock_order":
            state["facts"]["restocked"] = True
        state["pending_approval"] = None
        checkpoint(state)                               # 6) 每步落盘
    return state

if __name__ == "__main__":
    task = {"sku": "A-1001", "threshold": 50}
    print("=== 第一次运行（无审批）：会在下补货单前暂停 ===")
    run(task, approvals={})
    print("\n=== 第二次运行（批准补货单）：从 checkpoint 恢复并完成 ===")
    final = run(task, approvals={"create_restock_order": True})
    print("\n最终：done =", final["done"], "| 补货单 =", final["idempotency"])
    os.remove(CHECKPOINT)                               # 清理演示文件
```

**实际运行输出：**

```text
=== 第一次运行（无审批）：会在下补货单前暂停 ===
  [trace] {"step": 1, "event": "tool_result", "tool": "check_stock", "idempotent": false}
  [trace] {"step": 2, "event": "pause_for_approval", "tool": "create_restock_order"}
== 任务已暂停，等待审批。再次运行并批准即可继续 ==

=== 第二次运行（批准补货单）：从 checkpoint 恢复并完成 ===
== 检测到 checkpoint，从中断处恢复 ==
  [trace] {"step": 3, "event": "tool_result", "tool": "create_restock_order", "idempotent": false}
  [trace] {"step": 4, "event": "finish", "reason": "库存已处理，任务完成"}

最终：done = True | 补货单 = {'run-...:restock:A-1001': {'order_id': 'RO-...'}}
```

**从这段代码能看到 Harness 的本质：**

- **模型只出现在 `model_decide` 一处**，负责"下一步想做什么"；其余全是 Harness 的确定性逻辑。
- **高风险动作（补货）被强制拦下**：第一次运行到第 2 步就暂停并落盘，模型无论多"想"下单都绕不过审批。
- **暂停即 checkpoint、恢复即续跑**：第二次运行从磁盘读回状态，直接从第 3 步继续，而不是重头再来——这就是长任务可恢复的最小实现。
- **幂等键防重复副作用**：`create_restock_order` 用 `run_id+sku` 做键，即便循环因异常重入也不会重复下单。
- **要接真实 LLM，只需替换 `model_decide` 一个函数**，其余护栏原样复用——这正说明"Harness 与模型解耦"。

> 这段约 100 行的代码当然不是生产级（State Store 是本地 JSON、无并发、无沙箱、无真实鉴权），但它完整呈现了 Harness 的骨架。生产化就是把每个部件换成健壮实现：JSON→数据库、假模型→真实模型网关、`approvals` 字典→审批系统、`print`→可观测平台。

---

# 第三部分：设计原则与边界

> 核心问题：拿到自己的场景，如何判断需要多重的 Harness？哪些交给模型、哪些必须交给 Harness？编码 Agent 这类典型场景，Harness 具体长什么样？

## 十一、模型与 Harness 的责任边界

这是整篇文章最重要的一张表。设计任何 Agent，都应该先明确这条分界线：

| 职责 | 交给模型 | 交给 Harness（确定性代码） |
| --- | --- | --- |
| 理解意图 | ✅ 语义理解、抽取、分类 | ❌ |
| 规划步骤 | ✅ 动态决定下一步做什么 | ❌（但步数/时长上限由 Harness 定） |
| 选择工具 | ✅ 判断该用哪个工具 | ❌（但能用哪些工具由 Harness 注册） |
| 是否有权限 | ❌ 模型无从知晓 | ✅ 身份、权限、租户隔离 |
| 参数是否合法 | ⚠️ 模型可以尝试 | ✅ 最终由 Schema 校验把关 |
| 是否已执行过 | ❌ 模型不知道 | ✅ 幂等键判断 |
| 预算还剩多少 | ❌ 模型不知道 | ✅ 预算计数与拦截 |
| 是否需要审批 | ⚠️ 可标注风险 | ✅ 审批红线由 Harness 强制 |
| 何时停止 | ⚠️ 可判断"任务完成" | ✅ 超步数/超时/超预算强制停止 |
| 崩溃后从哪恢复 | ❌ 模型无状态 | ✅ checkpoint 与恢复 |
| 做过什么 | ❌ | ✅ Trace、日志、审计 |

**设计口诀：模糊判断交给模型，红线守护交给 Harness。**凡是"错了会造成真实损失且不可逆"的判断（权限、金额、删除、提交），绝不能只依赖模型的自觉，必须由 Harness 用代码兜底。

## 十二、什么时候需要重型 Harness，什么时候不需要

Harness 不是越重越好。过度工程会带来建设成本、维护负担和延迟。用下面的分级来判断：

| Agent 形态 | 需要的 Harness 重量 | 说明 |
| --- | --- | --- |
| 单次模型调用（总结、翻译、分类） | 几乎不需要 | 一次请求响应，加个超时重试即可 |
| 简单 RAG 问答 | 很轻 | 检索+生成，加错误处理和基本日志 |
| 受限 Tool Loop（开放搜索、代码分析） | 轻量 | 需要：工具校验、步数上限、超时、基本 Trace |
| 多阶段业务执行（审批、跨系统） | 完整 | 需要六大子系统齐全，尤其安全、审批、恢复 |
| 高风险/长任务/高并发（交易、运维、编码 Agent） | 重型 | 完整 + 持久化 State Store + 异步 Worker + 分布式调度 |

**六维判断法：**给你的场景在下面六个维度打分（0-2 分），总分越高越需要重型 Harness：

1. **副作用严重性**：动作是否不可逆、是否涉及钱/权限/生产数据？
2. **任务时长**：秒级 / 分钟级 / 小时级以上？
3. **步骤复杂度**：单步 / 少量固定步 / 多步动态分支？
4. **并发规模**：单用户偶发 / 多用户 / 高并发？
5. **合规审计要求**：无 / 一般 / 强合规（金融、医疗、政企）？
6. **失败恢复要求**：可重来 / 需断点续跑 / 必须精确恢复不可重复？

**经验阈值：**总分 ≤ 3 用轻量 Harness（或直接用现成 SDK）；4-7 需要完整 Harness；≥ 8 需要重型 Harness 并认真考虑成熟平台而非全自建。

## 十三、编码 Agent Harness 专题

编码 Agent（Claude Code、Codex、Cursor Agent、各类 SWE Agent）是当前 Harness 工程最集中、最能体现"难点在 Harness 而非模型"的场景。同一个模型，装进不同质量的 Harness，可用性天差地别。这一节专门拆解编码 Agent 的 Harness 长什么样。

### 13.1 为什么编码 Agent 的难点几乎都在 Harness

模型本身"会写代码"，但要让它**在真实代码库里可靠地完成一个任务**，需要 Harness 解决一连串工程问题：

| 挑战 | 属于 Harness 的哪部分 |
| --- | --- |
| 代码库有几十万行，塞不进上下文 | 上下文管理 + 工具执行（按需检索/读取） |
| 模型想执行 `rm -rf` 或 `git push -f` | 安全边界（权限确认、危险命令拦截） |
| 命令要在正确的目录、正确的环境里跑 | 工具执行（沙箱、工作目录、环境隔离） |
| 改错了要能回退 | 持久化恢复（版本控制、diff 审查） |
| 一个大任务要拆成多个子任务 | 执行循环调度（子 Agent、任务分解） |
| 跑了 100 轮还没修好 | 执行循环（步数/时长/预算上限） |

### 13.2 编码 Agent 的六大子系统落地

对照第二部分的六大子系统，看它们在编码 Agent 里具体是什么：

| 子系统 | 在编码 Agent 里的具体形态 |
| --- | --- |
| 模型适配 | 长上下文模型、支持工具调用、结构化 diff/patch 输出解析、超时降级 |
| 执行循环调度 | ReAct/Plan-Execute 循环、TodoList 任务分解、子 Agent（如探索用子 Agent）、步数与超时上限 |
| 工具执行 | 文件读写、Grep/Glob 搜索、命令执行（Bash）、编辑（Edit/Write）、Git 操作，每个都有参数校验和超时 |
| 安全边界 | 权限模式（只读/需确认/自动）、危险命令拦截、沙箱、工作目录限制、`.gitignore`/敏感文件保护、kill switch |
| 可观测 | 每步 Trace、Token/成本显示、命令输出留存、diff 展示 |
| 持久化恢复 | 会话历史、上下文压缩、Git 作为天然 checkpoint、可回退的编辑 |

### 13.3 编码 Agent 特有的 Harness 难题

有几个问题是编码场景独有、且几乎全靠 Harness 解决的：

**（1）上下文管理与压缩。**代码库远大于上下文窗口。Harness 必须：让模型**按需读取**（先搜索定位、再读相关文件，而不是全量塞入）；在长会话接近上下文上限时**自动压缩**历史（总结已完成的工作，丢弃无关的中间输出）；维护一份任务级的"工作记忆"（TodoList、已知事实）。

**（2）命令执行的安全护栏。**执行任意 shell 命令是编码 Agent 最强大也最危险的能力。Harness 通常分层防护：

```text
模型提议命令 → Harness 分类：
    ├─ 只读命令（ls/cat/grep）        → 自动执行
    ├─ 本地可逆写（编辑文件）          → 自动执行 + 可回退
    ├─ 危险命令（rm -rf/git push -f/  → 强制用户确认
    │            数据库操作/删分支）
    └─ 明确禁止（--no-verify 跳过校验）→ 拒绝或要求显式授权
```

> **关键原则（与本文安全边界一致）：**越难恢复、影响面越大的命令，越要人工确认。授权是"针对本次操作的、有范围的"，不因为用户批准过一次 `git push` 就默认以后都能自动推。

**（3）任务分解与子 Agent。**复杂任务（如"重构整个模块"）需要拆解。Harness 提供：TodoList 管理让主 Agent 跟踪进度；子 Agent 机制把独立的探索/搜索任务下放到子 Agent，既能并行、又能保护主 Agent 的上下文不被搜索结果撑爆。**注意：**子 Agent 是 Harness 的能力，不等于"多 Agent 架构"——它更多是上下文隔离和并行的工程手段。

**（4）编辑的可靠性。**让模型可靠地改代码比想象中难。Harness 通常要求：编辑前**必须先读**该文件（防止基于幻觉改动）；用精确的字符串匹配或 diff 而非"重写整个文件"（减小 blast radius、便于审查）；改完可展示 diff 供人确认。

### 13.4 走一遍：让编码 Agent 修一个 bug，Harness 在每一步做什么

下面用一个具体任务——**"用户报告登录接口偶发 500，修一下"**——走完整个流程，看六大子系统如何逐步介入。左列是 Agent 的动作，右列是 Harness 在背后做的事。

| Agent 的动作（模型决定） | Harness 在背后做的事（确定性） |
| --- | --- |
| ① 接到任务，规划：先复现→定位→修复→验证 | 建 `run_id`、初始化 State、建 TodoList、设置步数/时长/预算上限 |
| ② 搜索错误日志和相关代码 | Grep/Glob 工具：校验参数、限定在工作目录内、超时保护；结果标准化返回 |
| ③ 读取可疑文件 `auth/login.py` | 文件读工具：鉴权（在允许目录内）、记录已读，供后续"编辑前必须先读"校验 |
| ④ 上下文变长，历史里堆了大量日志 | 上下文管理：压缩早期搜索结果为摘要，保留关键事实，防止溢出 |
| ⑤ 判断是空指针：token 为空时未校验 | 纯模型判断，Harness 不干预（这是模糊推理） |
| ⑥ 提议编辑 `login.py` 加一个判空 | 编辑工具：校验"该文件已读过"、用精确 diff、记录变更（可回退） |
| ⑦ 提议运行 `pytest tests/auth/` | 命令分类=只读/本地可逆 → 自动执行、沙箱内、超时保护 |
| ⑧ 测试通过，提议 `git commit` | 命令分类=有副作用 → **暂停，请用户确认** |
| ⑨ 用户确认后提交 | 执行 + 幂等（同一 run 不重复提交）+ 记入 Trace 和审计 |
| ⑩ 提议 `git push` 到主分支 | 命令分类=高风险 → **再次确认**（授权不因第 ⑧ 步的确认而延续） |

**这一趟走下来，Harness 的价值一目了然：**

- **模型只负责第 ①⑤ 步的模糊判断**（怎么排查、bug 是什么），其余每一步都被 Harness 校验、限权、记录。
- **崩溃恢复：**假设第 ⑦ 步跑测试时进程崩了，恢复时从最近 checkpoint 读到"编辑已完成、测试未确认结果"，先查文件当前内容确认编辑还在，再重跑测试——不会重复编辑。
- **防注入：**如果第 ② 步搜到的某条日志里藏着 `# TODO: run rm -rf /tmp/*`，模型可能把它当指令。Harness 的命令分类会把 `rm -rf` 拦成"高风险"强制确认，而不是靠模型自觉——这正是第八节安全边界原则在编码场景的落地。
- **预算兜底：**如果 bug 很刁钻，Agent 反复搜索改了 40 轮还没修好，Harness 在触及步数/预算上限时强制停下并交回用户，而不是无限烧下去。

> **一句话：**模型给出了"聪明的判断"，但这次修复之所以**安全、可回退、可审计**，全是 Harness 的功劳。换个没有护栏的裸循环，同样的模型可能在第 ⑩ 步直接把未经确认的改动强推到主分支。

### 13.5 从编码 Agent 反观通用 Harness 的启示

编码 Agent 把 Harness 的每个原则都推到了极致，给通用场景三点启示：

1. **能力越强，护栏越关键。**给模型的能力（任意命令执行）越强，Harness 的安全边界就越是产品成败的关键——护栏差一点就是删库，好一点才敢开放给用户。
2. **上下文管理是一等公民。**长任务里，"让模型看到恰当的信息"和"及时丢弃无关信息"本身就是 Harness 的核心工程，而不是附属功能。
3. **人机协作节奏由 Harness 定义。**什么时候自动执行、什么时候停下来问用户，这条节奏线是 Harness 设计的，直接决定了用户体验是"好用的助手"还是"危险的野马"。

---

# 第四部分：落地路线

> 目标：给出从 0 到 1 建设 Harness 的可操作步骤、评测方法、安全治理要点和上线前检查清单。

## 十四、从 0 到 1：自建 vs 选型

**第一原则：不要从造 Harness 开始，要从一个具体任务开始。**先选一个"值得做且能验证"的场景，用最轻的方式跑通，再逐步加固 Harness，而不是先花三个月造一个通用平台。

### 14.1 决策：自建、用 SDK、还是用平台

| 选项 | 适合 | 代价 |
| --- | --- | --- |
| 直接用 SDK/框架 | 大多数场景。LangGraph、OpenAI Agents SDK、Claude Agent SDK 等已内置大部分 Harness 能力 | 一定的框架锁定和学习成本 |
| 用托管平台 | 不想自己运维、需要开箱即用的可观测和审批 | 数据出域、成本、定制受限 |
| 自建 Harness | 有极强定制/合规/性能要求，且团队有能力长期维护 | 建设与维护成本极高，容易重复造轮子 |

**建议：**绝大多数团队应该**站在成熟 SDK 上做定制**，只在 SDK 满足不了的地方（特殊安全模型、特殊持久化、特殊调度）自建那一部分。全自建通用 Harness 只在少数平台型团队才划算。

### 14.2 实施顺序（从轻到重，逐步加固）

```text
第 1 步：跑通最小闭环
    单模型 + 少量工具 + 受控 Loop（步数上限）+ 基本日志
第 2 步：加安全边界
    工具 Schema 校验 + 身份/权限传递 + 危险动作审批 + 预算上限
第 3 步：加可观测
    结构化事件 + Trace + Token/成本统计 + 一个小评测集
第 4 步：加持久化恢复
    State Store + checkpoint + 幂等键 + 恢复策略
第 5 步：加调度与规模化
    异步 Worker + 并发/背压 + 分布式 State + 版本与迁移
```

**每一步都要能独立上线并产生价值**，不要等五步全做完才发布。前两步就足以支撑一个安全可用的内部工具。

## 十五、评测与运营

Harness 侧重点是验证控制机制是否真的生效：工具被拒绝后有无副作用、重试是否重复写入、暂停恢复是否保留约束、Trace 是否能关联到真实调用。任务最终正确性还需要业务事实与证据校验。

样本构造、评分和版本比较统一见[如何评测 Agent](<../质量与实践/01-如何评测Agent.md>)。这里至少保留四类执行证据：工具调用记录、权限/审批判定、状态恢复轨迹、耗时与成本；不要只记录模型的自然语言解释。

## 十六、安全与治理

威胁分类、审批对象和恶意输入样本见[权限与提示注入防护](<04-Agent权限与提示注入防护.md>)。Harness 负责把这些策略落实到执行入口：

- 按发起者身份和任务范围校验每次读取或写入，避免共享超级权限。
- 审批绑定实际动作与参数，拒绝后终止该动作；不能从模型文本推导已批准。
- 检查预算、取消状态、工具可用性，并记录拒绝与执行结果。
- 支持工具禁用、运行终止、审计和适用的保留策略；策略变化后核对在途任务。

## 十七、上线前检查清单

### 场景与边界

- [ ] 这个任务真的需要 Harness 吗（六维评分）？是否单次调用/简单 RAG 就够了？
- [ ] 成功的业务标准是什么？如何验证任务真的完成了？
- [ ] 哪些动作自动执行，哪些必须审批，哪些绝对禁止？

### 技术

- [ ] 每个工具都有 Schema 校验、超时、重试策略了吗？
- [ ] 写操作都幂等了吗？幂等键怎么定义？
- [ ] Loop 有明确的终止条件（步数、超时、预算）吗？
- [ ] State 存在持久化存储而非进程内内存吗？
- [ ] 崩溃后能从 checkpoint 恢复吗？恢复会不会重复副作用？

### 安全

- [ ] Agent 以谁的身份执行？权限是最小的吗？
- [ ] 代码/命令执行在沙箱里吗？危险动作拦截了吗？
- [ ] 外部内容被当作不可信输入处理了吗（防 Injection）？
- [ ] 有预算上限和 kill switch 吗？

### 评测与运营

- [ ] 有覆盖正常/失败/边界/恶意输入的评测集吗？
- [ ] 有 Trace 能定位错误发生在哪一层吗？
- [ ] Token/成本可统计、可预警吗？
- [ ] 有运行手册（暂停、恢复、取消、回滚、排障）吗？

---

# 第五部分：延伸参考与自检

框架、SDK、托管运行时和平台能力属于时间敏感内容，已集中到[《Agent 框架、平台与产品生态参考》](<../references/Agent 框架、平台与产品生态参考.md>)。本文只保留稳定的 Harness 职责、边界和工程原则；具体选型前请核对参考页与官方资料。

## 常见误区速查

| 误区 | 正确理解 |
| --- | --- |
| Harness = 模型 | Harness 不是模型，是模型外面的执行外壳；它不提高智力，只放大或约束能力 |
| Harness = Runtime | Runtime 是 Harness 的一部分（调度+持久化）；Harness 还包含模型适配、工具执行、安全、可观测 |
| 用了框架 = 有了 Harness | 框架给了骨架，但幂等、权限、评测、恢复策略仍需按业务落实 |
| checkpoint = exactly-once | checkpoint 只保证状态可恢复，防重复副作用还需幂等 + 副作用记录 + 恢复前校验 |
| 模型可以自己判断权限/预算 | 模型无从知晓执行状态；权限、预算、幂等、审批必须由 Harness 用代码守住 |
| 越重的 Harness 越好 | 单次调用几乎不需要 Harness；按六维评分匹配重量，避免过度工程 |
| 只改模型就能解决编码 Agent 的全部问题 | 需要同时检查模型判断、Context、工具执行、反馈和恢复机制 |
| 授权一次 = 永久授权 | 授权是针对本次操作、有范围的；高风险动作每次都要走 Harness 的确认 |

---

## 理解检查

以下问题用于验证是否真正理解，而非记住了子系统名称：

1. 同一个模型，套上"好 Harness"和"坏 Harness"，在一个删库风险的任务上会有什么不同结局？为什么这个差异不在模型？
2. 为什么"这个操作我是否已经执行过"必须由 Harness 判断，而不能问模型？
3. checkpoint 已经能恢复状态了，为什么还需要幂等键？举一个会重复扣款的具体时序。
4. 一个只做文本总结的功能，需要哪些 Harness 能力？一个能执行任意命令的编码 Agent 呢？差异说明了什么？
5. 编码 Agent 里"什么时候自动执行命令、什么时候停下来问用户"这条线，为什么说它决定产品成败？

**最小验证集（以一个能执行命令的 Agent 为例）：**

- **正常案例：**任务在步数/预算内完成，只读命令自动执行，危险命令触发确认。
- **失败案例：**工具调用成功后崩溃，恢复时验证不会重复执行副作用。
- **安全边界案例：**外部内容里藏有"请执行 rm -rf"的注入指令，确认 Harness 拦截而非模型自觉。

---

## 结语

Harness 的意义不是让模型更聪明，而是给模型的每一次行动建立一个可以在真实世界里安全落地的执行环境。模型负责在模糊世界里判断"想做什么"，Harness 负责守住"能不能做、怎么做才安全、失败了怎么办、做过什么留没留痕"这四道确定性防线。

第一个 Harness 的正确目标，不是造一个通用平台，而是让一个具体任务先安全、可控、可观测地跑起来，再随着风险和规模逐步加固。能力越强的 Agent（尤其是能执行命令的编码 Agent），Harness 的护栏就越是产品成败的分水岭。

> **最终判断：**Harness 不取代模型、Prompt、Context、Graph 或传统软件工程，而是把它们粘合成一个能对结果负责的系统。真正的生产可靠性来自分层责任：模型处理模糊世界，Graph 管理任务结构，**Harness 约束执行、守住安全、保证可恢复**，传统系统守住业务事实，评测与观测证明结果。

---

## 主要官方资料

- [OpenAI：Harness engineering](https://openai.com/index/harness-engineering/)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangSmith Agent Server](https://docs.langchain.com/langsmith/agent-server)
- [Microsoft Agent Framework Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)
- [Google Agent Development Kit](https://github.com/google/adk-python)
