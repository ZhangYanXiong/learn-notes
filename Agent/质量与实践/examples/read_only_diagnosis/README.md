# 只读订单接口诊断：最小 Agent Loop

此例用 Python 标准库运行。`DemoPolicy` 是确定性模拟模型，方便复现每一步；它不代表真实 LLM 的推理能力。替换为模型接口时，仍需保持 `run` 中的动作、权限、工具结果和完成条件校验。

**验证范围：**这里的测试验证控制流程、证据判定和工具权限。注入文本样本使用模拟策略，不能据此判断真实模型对恶意指令的抵抗能力；接入真实模型后需要增加端到端评测。

```bash
python3 质量与实践/examples/read_only_diagnosis/agent.py
python3 -m unittest discover -s 质量与实践/examples/read_only_diagnosis -p 'test_*.py'
```

从 Agent 根目录运行上述命令。案例展示四个边界：

1. Context 只向策略提供 Goal、已验证观察、允许工具和剩余步数。
2. 策略返回 `call_tool` 或 `respond` 候选动作；程序决定是否可执行。
3. State 保存观察及来源；最终结论要求指标和日志两类证据。
4. 工具返回中的“重启服务”文本不产生权限；写工具请求会被拒绝。

练习：把 `DemoPolicy` 替换为真实模型调用后，新增 Schema 解析错误与工具超时样本；再把完整日志改为 Artifact 引用，只把相关片段送入 Context。对照 [Context Engineering](<../../../基础机制/04-如何构造上下文.md>)、[State/RAG/Memory](<../../../基础机制/05-State、RAG与Memory怎么分工.md>)和[Evaluation](<../../01-如何评测Agent.md>)检查你的实现。
