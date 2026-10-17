# AI 学习笔记

这个仓库整理 AI Agent 的基础概念、工程实践与框架调研。内容以 Markdown 文档为主，另附一个使用 Python 标准库运行的教学示例。

## 从哪里开始

- **系统学习 Agent：**从 [Agent 学习地图](<Agent/README.md>)开始，按基础机制、编排与协作、运行与连接、质量与实践的顺序阅读。
- **带着问题查找：**使用 [Agent 知识点索引](<Agent/知识点索引.md>)定位具体章节；术语和文档归属见 [术语与文档约定](<Agent/references/术语与文档约定.md>)。
- **动手练习：**查看 [只读订单接口诊断案例](<Agent/质量与实践/examples/read_only_diagnosis/README.md>)，运行一个使用模拟策略的最小 Agent Loop。
- **了解具体框架：**阅读 [DeepSeek Harness 架构调研](<deepseek-harness/deepseek-harness-调研报告.md>)及 [dsh 与 Hermes Agent 对比](<deepseek-harness/dsh-vs-hermes-对比.md>)。

## 目录

| 路径 | 内容 |
| --- | --- |
| [`Agent/`](<Agent/README.md>) | Agent 的 Loop、工具调用、目标与计划、Context、State/RAG/Memory、Graph、Harness、MCP、A2A、安全与评测等主题。 |
| [`Agent/质量与实践/examples/read_only_diagnosis/`](<Agent/质量与实践/examples/read_only_diagnosis/README.md>) | 可运行的只读诊断示例及测试。 |
| [`deepseek-harness/`](<deepseek-harness/deepseek-harness-调研报告.md>) | DeepSeek Harness 架构分析和与 Hermes Agent 的横向对比。 |

## 运行示例

在仓库根目录执行，无需安装第三方 Python 包：

```bash
python3 Agent/质量与实践/examples/read_only_diagnosis/agent.py
python3 -m unittest discover -s Agent/质量与实践/examples/read_only_diagnosis -p 'test_*.py'
```

示例中的 `DemoPolicy` 是确定性模拟策略，用于展示执行流程和权限边界，不代表真实模型的推理或安全表现。详情和练习说明见[示例 README](<Agent/质量与实践/examples/read_only_diagnosis/README.md>)。

## 阅读说明

Agent 主题文档的主要入口是 [Agent 学习地图](<Agent/README.md>)；框架、产品和协议的版本信息可能随时间变化，使用调研结论前请核对对应文档的基线日期及最新官方资料。
