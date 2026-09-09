"""安装的真实 OpenAI SDK + HTTP MockTransport；不连接互联网、不消耗 API 额度。"""
import json

import httpx
from openai import OpenAI

from harness.core import ResponsesAgent, Tool, ToolRegistry, object_schema
from harness.fakes import call, reply, response


def test_real_sdk_responses_wire_format():
    requests = []
    scripted = iter([response(call("sum", {"a": 20, "b": 22})), response(reply("42"))])
    def transport(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.url.path == "/v1/responses"
        data = next(scripted)
        data.update(created_at=0, model="test-model", tools=body["tools"],
                    parallel_tool_calls=False)
        return httpx.Response(200, json=data)
    client = OpenAI(api_key="test-not-a-real-key", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    tool = Tool("sum", "求和", object_schema({"a": {"type": "integer"},
                                             "b": {"type": "integer"}}), lambda a, b: a + b)
    try:
        result = ResponsesAgent(client, "test-model", ToolRegistry([tool])).run("求和")
    finally:
        client.close()
    assert result.status == "completed" and result.text == "42"
    assert requests[0]["tools"][0]["strict"] is True
    assert "function" not in requests[0]["tools"][0]
    output = requests[1]["input"][-1]
    assert output["type"] == "function_call_output" and output["call_id"] == "call_1"
    assert json.loads(output["output"]) == {"ok": True, "result": 42}
