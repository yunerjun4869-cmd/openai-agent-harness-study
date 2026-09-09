"""统一课程参数；不自动安装依赖、不在离线模式读取 API Key。"""
import argparse
import json
import os
import sys
from pathlib import Path

from .config import DEFAULT_MODEL, ROOT, live_client, load_config
from .core import DEFAULT_INSTRUCTIONS, ResponsesAgent, ToolRegistry
from .fakes import ScriptedClient


def lesson_args(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--demo", action="store_true", help="使用明确标识的离线脚本响应")
    parser.add_argument("--prompt", help="真实模型模式使用的自定义任务")
    parser.add_argument("--workspace", type=Path, default=ROOT / ".workspaces",
                        help="工具工作目录（默认 openai/.workspaces）")
    parser.add_argument("--allow-write", action="store_true", help="授权本章提供的写入或命令工具")
    return parser.parse_args()


def approve_tool(tool, arguments):
    """非交互输入直接拒绝；调用者也可用已确认的 --allow-write 提供授权。"""
    if not sys.stdin.isatty():
        return False
    print(f"\n请求执行：{tool.name}")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    return input("允许这次操作？输入 y 确认，其余拒绝：").strip().lower() == "y"


def make_client(demo_responses, demo):
    if demo:
        print("[离线演示] 模型响应为预设脚本；工具在本地真实执行，不产生 API 费用。")
        return ScriptedClient(demo_responses)
    try:
        return live_client()
    except (RuntimeError, ImportError) as exc:
        raise SystemExit(str(exc)) from exc


def run_example(tools, prompt, demo_responses, args, instructions=DEFAULT_INSTRUCTIONS):
    client = make_client(demo_responses, args.demo)
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL) if args.demo else load_config()["model"]
    registry = ToolRegistry(tools, allow_writes=args.allow_write,
                            approve=None if args.demo else approve_tool)
    result = ResponsesAgent(client, model, registry, instructions=instructions).run(prompt)
    names = {item["call_id"]: item["name"] for item in result.history
             if item.get("type") == "function_call"}
    for item in result.history:
        if item.get("type") == "function_call_output":
            value = json.loads(item["output"])
            label = "成功" if value.get("ok") else value.get("error", "失败")
            print(f"[工具] {names[item['call_id']]} → {label}")
    print(f"[状态] {result.status}\n{result.text}")
    print("[用量]", json.dumps(result.usage, ensure_ascii=False))
    if result.status != "completed":
        raise SystemExit(1)
    return result
