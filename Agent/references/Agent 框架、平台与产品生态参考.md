# Agent 框架、平台与产品生态参考

**整理日期：**2026-09-22　｜　**性质：**时间敏感参考资料，不作为稳定概念定义

> **使用提醒：**本页从 Agent Graph 与 Agent Harness 文档中集中迁移而来。框架 API、许可证、托管产品名称和能力变化较快，实际选型前必须核对官方文档、版本、部署区域、合规要求和价格。

> **返回主线：**[学习地图](<../README.md>)｜[Agent Graph](<../编排与协作/01-什么时候需要Agent Graph.md>)｜[Agent Harness](<../运行与连接/01-Agent Harness负责什么.md>)｜[Graph Engineering](<../编排与协作/02-如何实现Agent Graph.md>)

---
# 第一部分：Graph 与编排视角

> 本部分适合在技术选型时查阅，不需要通读。

## 一、代码型框架

| 产品 | 特点 | 适合 | 主要边界 |
| --- | --- | --- | --- |
| LangGraph | 显式 StateGraph、条件边、循环、checkpoint、HITL | 复杂状态、长任务、精细控制 | 偏底层，团队需自行设计治理与评测 |
| Microsoft Agent Framework | Executor + Edge 有向图，多 Agent 编排，Python/.NET | 微软技术栈和 Azure 企业项目 | 不同语言能力需逐项核对 |
| Google ADK | Sequential、Parallel、Loop、多 Agent、评测与部署 | Gemini、GCP、多模态、A2A | 离开 GCP 后需自行补运行治理 |
| OpenAI Agents SDK | Agent Loop、Tool、Handoff、Guardrail、Tracing | 轻量工具型 Agent、handoff、语音 | 不是显式 Graph DSL，复杂图需应用代码 |
| CrewAI | Crew 表达角色团队，Flow 表达结构化流程 | 角色分工明显的快速原型 | 过度拆 Agent 会增加成本与不确定性 |
| LlamaIndex Workflows | 事件驱动、共享状态、循环、并行、checkpoint | RAG、文档和数据密集型 Agent | 企业权限与业务连接需自行集成 |

## 二、可视化与自部署平台

| 产品 | 定位 | 注意事项 |
| --- | --- | --- |
| Dify | Workflow/Chatflow、RAG、Agent、模型管理和 API | 采用带附加条件的修改许可证，多租户和品牌场景需核对授权 |
| Coze Studio | Agent、Workflow、RAG、Plugin、Database 和可视化画布 | 开源版与商业版功能不同，公网部署需重点检查代码节点与权限隔离 |
| Flowise | 面向 LLM Chain 和 AgentFlow 的可视化编排 | 社区部分和 enterprise 目录许可证不同 |
| n8n | 传统自动化图中嵌入 AI Agent 节点，连接器丰富 | 属于 fair-code/source-available，不是标准开源许可证 |

## 三、商业托管平台

| 平台 | 核心能力 | 更适合 |
| --- | --- | --- |
| LangSmith Deployment | Agent Server、持久化、线程、队列、Trace、评测和部署 | LangGraph/LangChain 团队 |
| Microsoft Foundry Agent Service / Copilot Studio | 托管 Agent、身份、连接器、扩缩容、观测与 M365 集成 | Azure、M365、Dynamics 和 Power Platform |
| Google Gemini Enterprise Agent Platform | ADK、Agent Studio、Runtime、评测、治理和模型平台 | Google Cloud、Gemini、多模态与企业治理 |
| Amazon Bedrock AgentCore | Runtime、Memory、Gateway、Identity、Browser、Code Interpreter、Observability | AWS 上使用任意框架或模型的企业应用 |
| Salesforce Agentforce | CRM 数据、Flow、权限、业务对象与 Agent Graph | 客服、销售和 CRM 核心流程 |
| 国内云平台 | 阿里云百炼、腾讯云 ADP、百度千帆等提供低代码、知识库与托管运行 | 国内数据合规、私有化和渠道集成 |

## 四、当前应用成熟度

Agent Graph 已从研究原型进入生产工具阶段，但成熟方式不是"完全自主"。当前更可靠的生产组合是：

```text
固定 Graph 主干 + 少量 LLM 判断节点 + 白名单工具 + checkpoint + 人工审批 + Trace + 离线/在线评测
```

已经公开的落地方向主要集中在客服、物流、事故管理、财务运营、企业研究、文档处理和研发运维。

## 五、企业级参考架构

1. **入口层：**Web、IM、API、定时任务和业务事件。
2. **身份与策略层：**用户身份透传、租户隔离、工具白名单和风险策略。
3. **Graph 编排层：**State Schema、节点、边、循环、并行、checkpoint、暂停与恢复。
4. **模型网关：**模型路由、限流、预算、缓存、Prompt 与模型版本。
5. **知识层：**文档解析、索引、检索、权限过滤、来源和时效。
6. **工具网关：**Schema、身份、授权、幂等、超时、网络出口和审计。
7. **状态与数据层：**会话库、checkpoint 库、业务数据库、向量库和长期记忆。
8. **AgentOps：**Trace、评测、日志、告警、成本、版本、灰度和回滚。

## 六、选型建议

- **复杂状态和核心 Agent 产品：**LangGraph 或 Microsoft Agent Framework。
- **Google Cloud/Gemini/多模态：**Google ADK + Agent Platform。
- **轻量工具调用、handoff 和语音：**OpenAI Agents SDK。
- **RAG 和文档密集：**LlamaIndex Workflows。
- **业务与研发共同做 PoC：**Dify、Coze Studio 或 Flowise。
- **跨 SaaS 自动化：**n8n，在确定性流程中嵌入少量 Agent 判断。
- **已有框架，只缺生产基础设施：**评估 LangSmith Deployment、Microsoft Foundry、Google Agent Platform 或 AWS AgentCore。

> 推荐默认路线：单 Agent + 混合状态图 + 确定性工具 + 人工审批 + 离线评测 + 影子模式。

---

---

# 第二部分：Harness 与托管运行视角

> 本部分适合在技术选型时查阅，不需要通读。这里的"框架/平台"多数同时承担 Graph 编排和 Harness 执行两类职责，选型时要分别看它们的 Harness 能力（工具执行、安全、可观测、恢复）是否够用。

## 七、框架与 SDK：内置了哪些 Harness 能力

选框架时，别只看"能不能画图"，更要看它替你解决了多少 Harness 工作：

| 产品 | 内置的 Harness 能力 | 主要边界 |
| --- | --- | --- |
| LangGraph | StateGraph、checkpoint、HITL 审批、持久化恢复、Trace（配合 LangSmith） | 偏底层，权限/评测/治理需自行补 |
| OpenAI Agents SDK | Agent Loop、Tool、Handoff、Guardrail（护栏）、Tracing | 非显式 Graph，复杂图靠应用代码 |
| Claude Agent SDK | 工具执行、权限模式、子 Agent、上下文管理，面向编码/通用 Agent | 生态较新，企业级治理需自行补 |
| Microsoft Agent Framework | Executor+Edge 编排、多 Agent、Python/.NET | 不同语言能力需逐项核对 |
| Google ADK | Sequential/Parallel/Loop、评测、部署、A2A | 离开 GCP 需自补运行治理 |
| CrewAI | 角色团队（Crew）+ 结构化流程（Flow） | 过度拆 Agent 会增加成本与不确定性 |
| LlamaIndex Workflows | 事件驱动、共享状态、循环、checkpoint | 企业权限与业务连接需自行集成 |

## 八、托管平台：把 Harness 当基础设施买

当你不想自己运维 Harness 的运行时、可观测和审批时，可选托管平台：

| 平台 | 提供的 Harness 基础设施 | 更适合 |
| --- | --- | --- |
| LangSmith Deployment | Agent Server、持久化、线程、队列、Trace、评测 | LangGraph/LangChain 团队 |
| Microsoft Foundry Agent Service | 托管运行、身份、连接器、扩缩容、观测、M365 集成 | Azure、M365 生态 |
| Google Gemini Enterprise Agent Platform | Runtime、评测、治理、模型平台 | GCP、Gemini、企业治理 |
| Amazon Bedrock AgentCore | Runtime、Memory、Gateway、Identity、Browser、Code Interpreter、Observability | AWS 上任意框架/模型 |
| Salesforce Agentforce | CRM 数据、权限、业务对象、流程 | 客服、销售、CRM 流程 |
| 国内云平台 | 阿里云百炼、腾讯云 ADP、百度千帆等，低代码 + 托管运行 | 国内合规、私有化 |

## 九、参考架构与选型建议

### 9.1 以 Harness 为中枢的参考架构

```text
入口层：Web / IM / API / 事件
    ↓
身份与策略层：身份透传、租户隔离、工具白名单、风险策略
    ↓
【Harness 中枢】
    ├─ 模型网关：路由、限流、预算、缓存、Prompt/模型版本
    ├─ 执行引擎：Loop/Graph 调度、会话、State、并发、超时
    ├─ 工具网关：Schema、鉴权、幂等、超时、网络出口、审计
    ├─ 安全护栏：沙箱、审批、kill switch、危险动作拦截
    └─ 可观测：事件流、Trace、Token/成本、评测
    ↓
状态与数据层：会话库、checkpoint 库、业务库、向量库、Memory
    ↓
传统业务系统：数据库、事务、队列、IAM、审计
```

### 9.2 选型建议

- **复杂状态、长任务、需要精细恢复：**LangGraph（+ LangSmith 做可观测和部署）。
- **轻量工具型 Agent、handoff、护栏：**OpenAI Agents SDK。
- **编码 / 通用工具 Agent，需要权限模式和子 Agent：**Claude Agent SDK。
- **微软 / Azure 生态：**Microsoft Agent Framework + Foundry。
- **GCP / Gemini / 多模态：**Google ADK + Agent Platform。
- **已有框架，只缺生产级 Harness 基础设施：**评估 LangSmith Deployment、Foundry、Google Agent Platform 或 AWS AgentCore。

> 推荐默认路线：站在成熟 SDK 上定制，先跑通"受控 Loop + 安全边界"，再逐步补齐可观测和持久化，只在 SDK 满足不了的地方自建。

---
---

# 第三部分：选型使用规则

1. 先确定任务需要单次调用、Loop、Workflow 还是 Graph，再选框架。
2. 把能力拆成 Graph、Harness、模型、工具、知识和托管运行六个维度核对，不使用“支持 Agent”作为充分条件。
3. 用最小 PoC 验证 State、暂停恢复、工具权限、幂等、Trace、评测和部署，而不是只验证 Demo 能运行。
4. 对许可证、私有化、数据驻留、网络出口、身份集成和可观测能力做单独核验。
5. 每次更新产品信息时记录核验日期和官方来源；稳定概念不要依赖具体产品名称。

