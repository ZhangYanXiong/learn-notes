"""Dependency-free, read-only Agent Loop learning example.

DemoPolicy stands in for a model. The application, not the policy, owns
authorization, tool execution, state updates and completion checks.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class State:
    goal: str = "Diagnose orders API latency without changing production"
    observations: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    status: str = "running"


def read_metrics() -> dict:
    return {"source": "metrics", "observed_at": "2026-10-16T10:00:00+08:00",
            "pool_utilization_pct": 100, "latency_p95_ms": 2400}


def read_logs() -> dict:
    return {"source": "logs", "observed_at": "2026-10-16T10:00:00+08:00",
            "events": ["connection pool exhausted", "request timed out"]}


READ_TOOLS: dict[str, Callable[[], dict]] = {
    "read_metrics": read_metrics,
    "read_logs": read_logs,
}


class DemoPolicy:
    """A deterministic stand-in for one model decision per loop iteration."""

    def decide(self, context: dict) -> dict:
        seen = context["observations"]
        if "metrics" not in seen:
            return {"action": "call_tool", "tool": "read_metrics"}
        if "logs" not in seen:
            return {"action": "call_tool", "tool": "read_logs"}
        return {"action": "respond"}


def build_context(state: State, remaining_steps: int) -> dict:
    """Project only the current decision's required state, not the full trace."""
    return {"goal": state.goal, "observations": dict(state.observations),
            "allowed_tools": tuple(READ_TOOLS), "remaining_steps": remaining_steps}


def assessment(state: State) -> tuple[str, str]:
    metrics = state.observations.get("metrics")
    logs = state.observations.get("logs")
    if not metrics or not logs:
        return ("insufficient_evidence",
                "证据不足：需要指标和日志两类独立来源；当前只给出已观察事实。")
    if (metrics.get("pool_utilization_pct", 0) >= 95
            and "connection pool exhausted" in logs.get("events", [])):
        return ("completed", "最可能是连接池耗尽。证据：指标显示连接池使用率 "
                f"{metrics['pool_utilization_pct']}%（{metrics['observed_at']}）；"
                f"日志出现连接池耗尽（{logs['observed_at']}）。"
                "这是只读诊断，尚未验证根本触发原因。")
    return ("insufficient_evidence", "两类证据尚不能支持同一原因；需要继续只读调查。")


def valid_tool_result(source: str, result: object) -> bool:
    if not isinstance(result, dict) or result.get("source") != source:
        return False
    if not isinstance(result.get("observed_at"), str):
        return False
    if source == "metrics":
        return (type(result.get("pool_utilization_pct")) is int
                and 0 <= result["pool_utilization_pct"] <= 100)
    return (isinstance(result.get("events"), list)
            and all(isinstance(event, str) for event in result["events"]))


def run(policy=None, tools=None, max_steps: int = 3) -> tuple[State, str]:
    """Run a bounded loop. A model's candidate action never grants permission."""
    policy = policy or DemoPolicy()
    tools = READ_TOOLS if tools is None else tools
    state = State()

    for step in range(max_steps):
        candidate = policy.decide(build_context(state, max_steps - step))
        action = candidate.get("action") if isinstance(candidate, dict) else None
        if action == "call_tool":
            name = candidate.get("tool")
            if name not in READ_TOOLS or name not in tools:
                state.status = "blocked"
                state.trace.append({"event": "tool_rejected", "tool": name})
                return state, "请求了未授权工具，诊断已停止。"
            expected_source = name.removeprefix("read_")
            # This fixture returns one fixed observation per source; repeat reads add no evidence.
            if expected_source in state.observations:
                state.status = "blocked"
                state.trace.append({"event": "duplicate_tool", "tool": name})
                return state, "重复读取未产生进展，诊断已停止。"
            try:
                result = tools[name]()
            except Exception as exc:
                state.status = "failed"
                state.trace.append({"event": "tool_error", "tool": name,
                                    "error_type": type(exc).__name__})
                return state, f"读取 {name} 失败；未执行任何写操作。"
            if not valid_tool_result(expected_source, result):
                state.status = "failed"
                state.trace.append({"event": "invalid_result", "tool": name})
                return state, "工具结果缺少可信来源，诊断已停止。"
            state.observations[expected_source] = result
            state.trace.append({"event": "tool_result", "tool": name,
                                "source": expected_source})
        elif action == "respond":
            state.status, answer = assessment(state)
            state.trace.append({"event": "respond", "status": state.status})
            return state, answer
        else:
            state.status = "blocked"
            state.trace.append({"event": "invalid_action"})
            return state, "无效动作，诊断已停止。"

    state.status, answer = assessment(state)
    state.trace.append({"event": "step_limit"})
    return state, answer


if __name__ == "__main__":
    final_state, answer = run()
    print(f"状态：{final_state.status}\n{answer}\n轨迹：{final_state.trace}")
