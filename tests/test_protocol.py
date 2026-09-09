"""协议测试使用脚本模型；SDK 序列化另外使用 HTTP mock 验证。"""
import json

import pytest

from harness.core import ResponsesAgent, Tool, ToolRegistry, object_schema
from harness.fakes import ScriptedClient, call, reply, response


def agent_with(script, handler=lambda value: value, **kwargs):
    tool = Tool("record", "记录整数", object_schema({"value": {"type": "integer"}}),
                lambda value: handler(value))
    client = ScriptedClient(script)
    return ResponsesAgent(client, "test-model", ToolRegistry([tool]), **kwargs), client


def test_replays_reasoning_and_every_call_output():
    reasoning = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque"}
    agent, client = agent_with([
        response(reasoning, call("record", {"value": 1}), call("record", {"value": 2}, "call_2")),
        response(reply("已完成")),
    ])
    result = agent.run("记录两个值")
    second = client.requests[1]["input"]
    assert second[1] == reasoning
    calls = [item["call_id"] for item in second if item.get("type") == "function_call"]
    outputs = [item["call_id"] for item in second if item.get("type") == "function_call_output"]
    assert calls == outputs == ["call_1", "call_2"]
    assert result.status == "completed"
    assert all(request["store"] is False for request in client.requests)


@pytest.mark.parametrize("arguments", ['{"value":"bad"}', '{broken', '{"value":1,"extra":1}'])
def test_invalid_arguments_are_paired_error_results(arguments):
    effects = []
    item = call("record", {"value": 1})
    item["arguments"] = arguments
    agent, _ = agent_with([response(item), response(reply("修正参数"))], effects.append)
    result = agent.run("测试错误")
    assert effects == []
    output = next(i for i in result.history if i.get("type") == "function_call_output")
    assert json.loads(output["output"])["ok"] is False


def test_unknown_tool_and_handler_failure_still_have_outputs():
    def broken(value):
        raise RuntimeError("工具失败")
    agent, _ = agent_with([response(call("missing", {}), call("record", {"value": 1}, "call_2")),
                           response(reply("工具失败，无法确认完成"))], broken)
    result = agent.run("测试错误")
    outputs = [json.loads(i["output"]) for i in result.history if i.get("type") == "function_call_output"]
    assert len(outputs) == 2 and all(not item["ok"] for item in outputs)


def test_incomplete_never_runs_tools():
    effects = []
    agent, _ = agent_with([response(call("record", {"value": 1}), status="incomplete")], effects.append)
    assert agent.run("测试").status == "incomplete"
    assert effects == []


def test_duplicate_call_id_cannot_repeat_side_effect():
    effects = []
    agent, _ = agent_with([response(call("record", {"value": 1})),
                           response(call("record", {"value": 1}))], effects.append)
    result = agent.run("测试")
    assert result.status == "failed" and effects == [1]


def test_budgets_and_empty_response_never_claim_completion():
    agent, client = agent_with([response(reply("超预算"))], max_context_chars=1)
    assert agent.run("测试").status == "context_limit" and not client.requests
    agent, _ = agent_with([response(call("record", {"value": 1}))], max_turns=1)
    assert agent.run("测试").status == "budget_exceeded"
    agent, _ = agent_with([response()])
    assert agent.run("测试").status == "incomplete"
    effects = []
    agent, _ = agent_with([response(call("record", {"value": 1}),
                                    usage={"input_tokens": 5, "output_tokens": 10})],
                          effects.append, max_total_tokens=10)
    assert agent.run("测试").status == "budget_exceeded" and effects == []


def test_denial_and_hook_failure_do_not_execute():
    effects = []
    tool = Tool("write", "写入", object_schema({"value": {"type": "integer"}}), effects.append, True)
    registry = ToolRegistry([tool])
    assert registry.execute("write", '{"value":1}')["error"] == "PermissionDenied"
    def deny(event, payload):
        if event == "before":
            raise PermissionError("hook 拒绝")
    registry = ToolRegistry([tool], allow_writes=True, hooks=[deny])
    assert registry.execute("write", '{"value":1}')["ok"] is False
    assert effects == []


def test_after_hook_failure_preserves_executed_result():
    def hook(event, payload):
        if event == "after":
            raise RuntimeError("日志不可写")
    tool = Tool("record", "记录", object_schema({}), lambda: 42)
    registry = ToolRegistry([tool], hooks=[hook])
    assert registry.execute("record", "{}") == {"ok": True, "result": 42}
    assert registry.hook_errors == [{"event": "after", "error": "RuntimeError"}]


def test_duplicate_id_from_previous_run_is_rejected():
    effects = []
    agent, _ = agent_with([response(call("record", {"value": 1})), response(reply("已记录")),
                           response(call("record", {"value": 1}))], effects.append)
    first = agent.run("第一轮")
    second = agent.run("继续", history=first.history)
    assert first.status == "completed" and second.status == "failed"
    assert effects == [1]


def test_unpaired_history_and_malformed_call_are_rejected():
    agent, client = agent_with([])
    assert agent.run("继续", history=[call("record", {"value": 1})]).status == "failed"
    assert client.requests == []
    malformed = call("record", {"value": 1})
    del malformed["arguments"]
    agent, _ = agent_with([response(malformed)])
    assert agent.run("测试").status == "failed"


def test_authorization_requires_boolean_true_and_nullable_objects_are_strict():
    effects = []
    tool = Tool("write", "写入", object_schema({}), lambda: effects.append(1), True)
    registry = ToolRegistry([tool], approve=lambda *_: "no")
    assert registry.execute("write", "{}")["error"] == "PermissionDenied"
    assert effects == []
    bad = object_schema({"record": {"type": ["object", "null"],
                                    "properties": {"value": {"type": "string"}}}})
    with pytest.raises(ValueError, match="additionalProperties"):
        ToolRegistry([Tool("bad", "不合法 strict schema", bad, lambda: None)])
