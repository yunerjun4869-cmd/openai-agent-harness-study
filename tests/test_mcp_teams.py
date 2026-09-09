"""远程审批协议与团队隔离测试；不发出任何网络请求。"""
import json
from threading import Barrier, Lock

import httpx
from openai import OpenAI
import pytest

from harness.fakes import ScriptedClient, reply, response
from harness.mcp import remote_mcp_tool, run_remote_mcp
from harness.teams import run_team


def approval(identifier="approval_1", name="search_docs"):
    return {"type": "mcp_approval_request", "id": identifier,
            "name": name, "server_label": "course_docs", "arguments": '{"query":"test"}'}


def config():
    return remote_mcp_tool("https://mcp.example.test/mcp", ["search_docs"])


@pytest.mark.parametrize("decision", [True, False, None, "yes"])
def test_approval_is_explicit_and_next_input_is_only_new_output(decision):
    first = response({"type": "reasoning", "id": "rs_1", "summary": []}, approval())
    first["id"] = "resp_first"
    client = ScriptedClient([first, response(reply("已处理审批。"))])
    result = run_remote_mcp(client, "test-model", "查询", config(), lambda _: decision)
    assert result.status == "completed"
    assert [item["type"] for item in result.outputs] == ["reasoning", "mcp_approval_request", "message"]
    second = client.requests[1]
    assert second["previous_response_id"] == "resp_first"
    assert second["input"] == [{"type": "mcp_approval_response",
                                "approval_request_id": "approval_1", "approve": decision is True}]
    assert second["store"] is True
    assert second["instructions"] == client.requests[0]["instructions"]


def test_unlisted_tool_is_denied_without_asking_callback():
    client = ScriptedClient([response(approval(name="delete_all")), response(reply("已拒绝"))])
    run_remote_mcp(client, "test", "query", config(), lambda _: pytest.fail("不应询问越权工具"))
    assert client.requests[1]["input"][0]["approve"] is False


def test_incomplete_never_approves_partial_output():
    client = ScriptedClient([response(approval(), status="incomplete")])
    result = run_remote_mcp(client, "test", "query", config(), lambda _: pytest.fail("截断请求不得批准"))
    assert result.status == "incomplete"
    assert len(client.requests) == 1


def test_remote_error_and_empty_final_are_not_success():
    error = {"type": "mcp_call", "id": "mc_1", "error": "server unavailable"}
    result = run_remote_mcp(ScriptedClient([response(error, reply("服务异常"))]),
                            "test", "query", config(), lambda _: True)
    assert result.status == "failed"
    result = run_remote_mcp(ScriptedClient([response()]), "test", "query", config(), lambda _: True)
    assert result.status == "incomplete"


def test_remote_failure_precedes_other_approval_in_same_response():
    error = {"type": "mcp_call", "id": "mc_1", "error": "service failed"}
    client = ScriptedClient([response(error, approval()), response(reply("后续文本"))])
    result = run_remote_mcp(client, "test", "query", config(),
                            lambda _: pytest.fail("已有工具失败，不应继续审批"))
    assert result.status == "failed"
    assert len(client.requests) == 1


@pytest.mark.parametrize("url", ["http://example.test/mcp", "https://localhost/mcp", "https://user:pass@example.test/mcp"])
def test_mcp_rejects_unsupported_or_credential_urls(url):
    with pytest.raises(ValueError):
        remote_mcp_tool(url, ["search_docs"])


def test_real_sdk_serializes_mcp_approval_chain_without_network():
    requests = []
    payloads = [response(approval()), response(reply("SDK 协议成功"))]
    payloads[0]["id"] = "resp_sdk_first"

    def transport(request):
        requests.append(json.loads(request.content))
        payload = payloads[len(requests) - 1]
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        client = OpenAI(api_key="test-key-no-network", base_url="https://api.example.test/v1",
                        http_client=http_client, max_retries=0)
        result = run_remote_mcp(client, "test-model", "查询", config(), lambda _: True)
    assert result.status == "completed"
    assert result.text == "SDK 协议成功"
    assert requests[0]["tools"][0]["require_approval"] == "always"
    assert requests[0]["tools"][0]["type"] == "mcp"
    assert requests[1]["previous_response_id"] == "resp_sdk_first"
    assert requests[1]["input"][0]["approval_request_id"] == "approval_1"


def test_team_runs_concurrently_in_distinct_directories(tmp_path):
    barrier, lock = Barrier(2, timeout=3), Lock()
    active, peak = 0, 0

    def worker(name, prompt, directory):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        (directory / "own.txt").write_text(name, encoding="utf-8")
        barrier.wait()
        assert (directory / "own.txt").read_text(encoding="utf-8") == name
        with lock:
            active -= 1
        return str(directory)

    result = run_team({"reviewer": "review", "tester": "test"}, worker, tmp_path, max_workers=2)
    assert peak == 2
    assert list(result) == ["reviewer", "tester"]
    assert all(item["status"] == "completed" for item in result.values())
    assert result["reviewer"]["result"] != result["tester"]["result"]


def test_one_team_failure_preserves_other_result(tmp_path):
    def worker(name, prompt, directory):
        if name == "bad":
            raise ValueError("成员失败")
        return "保留的结果"

    result = run_team({"bad": "x", "good": "y"}, worker, tmp_path)
    assert result["bad"]["status"] == "failed"
    assert result["good"] == {"status": "completed", "result": "保留的结果"}


def test_team_rejects_escape_and_preexisting_symlink(tmp_path):
    with pytest.raises(ValueError):
        run_team({"../escape": "x"}, lambda *_: None, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "team"
    root.mkdir()
    (root / "member").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        run_team({"member": "x"}, lambda *_: None, root)
