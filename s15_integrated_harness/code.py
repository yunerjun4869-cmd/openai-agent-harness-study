"""s15：把文件、权限、审计、任务状态和预算接入同一循环。"""
from pathlib import Path
import json
import os
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import approve_tool, lesson_args, make_client
from harness.core import ResponsesAgent, ToolRegistry
from harness.fakes import call, reply, response
from harness.filesystem import Workspace
from harness.storage import TaskStore
from s10_task_system.code import task_tools


def main():
    args = lesson_args(__doc__)
    with tempfile.TemporaryDirectory(prefix="openai-s15-") as temporary:
        root = Path(temporary) if args.demo else args.workspace / "s15"
        workspace = Workspace(root / "files")
        store = TaskStore(root / "state" / "tasks.sqlite3")
        events = []

        def audit(event, payload):
            events.append({"event": event, "tool": payload["name"]})

        scripted = [
            response(call("task_create", {"task_id": "report", "title": "生成学习报告", "dependencies": []}, "integrated_1")),
            response(call("task_claim", {}, "integrated_2")),
            response(call("write_file", {"path": "report.md", "content": "# 学习报告\n\nResponses API 工具调用由宿主验证、授权和执行。\n"}, "integrated_3")),
            response(call("read_file", {"path": "report.md"}, "integrated_4")),
            response(call("task_complete", {"task_id": "report", "summary": "报告已写入并回读"}, "integrated_5")),
            response(reply("[模拟] 已生成 report.md 并回读，任务记录已更新，审计事件由宿主保留。")),
        ]
        if args.demo:
            print("[离线演示] 模型回复来自脚本；文件、SQLite、权限分发和审计实际运行。")
        registry = ToolRegistry(workspace.tools() + task_tools(store),
                                allow_writes=args.allow_write or args.demo,
                                approve=approve_tool, hooks=[audit])
        client = make_client(scripted, args.demo)
        agent = ResponsesAgent(client, os.getenv("OPENAI_MODEL", "gpt-6-astra"), registry,
                               max_turns=8, max_tool_calls=16, max_context_chars=40000,
                               instructions="用中文工作。先登记并认领任务，再生成报告、回读验证，最后更新任务记录。")
        result = agent.run(args.prompt or "生成简短的 Responses API 学习报告 report.md，并记录任务完成情况。已有报告就检查并总结。")
        print(f"状态：{result.status}\n{result.text}")
        print("审计：", json.dumps(events, ensure_ascii=False))
        print("任务：", json.dumps(store.list(), ensure_ascii=False))
        print("宿主观察到的文件：", workspace.list_files())
        if result.status != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
