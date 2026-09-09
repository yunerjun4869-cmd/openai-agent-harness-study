"""s14：OpenAI 托管的远程 MCP，逐次人工审批。"""
from pathlib import Path
import argparse
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import make_client
from harness.fakes import ScriptedClient, reply, response
from harness.mcp import remote_mcp_tool, run_remote_mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="完全离线，模拟 MCP 协议")
    parser.add_argument("--prompt", default="用允许的 MCP 工具查找 Responses API 文档，并说明信息来源。")
    parser.add_argument("--mcp-url", help="你自有的公开 HTTPS MCP 地址")
    parser.add_argument("--allowed-tool", action="append", help="准确的远程工具名称；可重复")
    parser.add_argument("--workspace", type=Path, help="兼容统一入口；本章不使用本地工作文件")
    parser.add_argument("--allow-write", action="store_true", help="兼容统一入口；不授予远程 MCP 审批权限")
    args = parser.parse_args()
    scripted = [
        response({"type": "mcp_list_tools", "id": "list_1", "server_label": "course_docs",
                  "tools": [{"name": "search_docs", "description": "模拟文档查询",
                             "input_schema": {"type": "object", "properties": {}}}]},
                 {"type": "mcp_approval_request", "id": "approval_1", "name": "search_docs",
                  "server_label": "course_docs", "arguments": '{"query":"Responses API"}'}),
        response({"type": "mcp_call", "id": "mcp_call_1", "server_label": "course_docs",
                  "name": "search_docs", "arguments": '{"query":"Responses API"}',
                  "output": "[模拟] Responses API 支持 function 与远程 MCP 工具。"},
                 reply("[模拟] 审批后获得了模拟文档结果；没有连接任何远程 MCP 服务。")),
    ]
    # MCP 演示连工具结果也是模拟值，不能复用“本地工具真实执行”的通用文案。
    client = ScriptedClient(scripted) if args.demo else make_client(scripted, False)
    url = args.mcp_url or os.getenv("MCP_SERVER_URL")
    allowed = args.allowed_tool or []
    if args.demo:
        print("[离线演示] 展示工具发现 → 审批请求 → 明示模拟批准 → 工具结果。")
        url, allowed = "https://mcp.example.invalid/mcp", ["search_docs"]
    elif not url or not allowed:
        parser.error("真实模式需要 --mcp-url 和至少一个 --allowed-tool；工具名由你的服务提供。")
    tool = remote_mcp_tool(url, allowed)

    def approve(request):
        print("MCP 审批请求：", json.dumps(request, ensure_ascii=False, indent=2))
        if args.demo:
            print("[模拟批准] 仅为离线协议演示；真实模式不会自动批准。")
            return True
        if not sys.stdin.isatty():
            print("当前终端无法交互，已拒绝请求。")
            return False
        print("此操作由 OpenAI 服务连接远程 MCP；参数将发给上述 MCP 服务。")
        try:
            return input("确认批准这一次工具调用？输入 y 批准，其余拒绝：").strip().lower() == "y"
        except (EOFError, KeyboardInterrupt):
            return False

    result = run_remote_mcp(client, os.getenv("OPENAI_MODEL", "gpt-6-astra"),
                            args.prompt, tool, approve)
    print(f"状态：{result.status}\n{result.text}")
    print("保留的完整输出项：", [item["type"] for item in result.outputs])
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
