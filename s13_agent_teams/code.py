"""s13：两个独立 Responses 会话在有界线程池中协作。"""
from pathlib import Path
import json
import os
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, make_client
from harness.core import ResponsesAgent, ToolRegistry
from harness.fakes import call, reply, response
from harness.filesystem import Workspace
from harness.teams import run_team


def main():
    args = lesson_args(__doc__)
    texts = {"reviewer": "权限边界：文件工具必须拒绝工作目录之外的路径。",
             "tester": "验收场景：正常读取、目录穿越、符号链接越界。"}
    tasks = {"reviewer": "读取 input.txt，说明设计风险。",
             "tester": "读取 input.txt，提出三个验收用例。"}
    if args.demo:
        print("[离线演示] 模型回复来自脚本；线程、独立目录和文件工具真实运行。")
    # 团队资料是固定的教学输入；临时目录也用于真实模式，退出后清理。
    with tempfile.TemporaryDirectory(prefix="openai-team-") as temporary:
        def worker(name, prompt, directory):
            (directory / "input.txt").write_text(texts[name], encoding="utf-8")
            client = make_client([
                response(call("read_file", {"path": "input.txt"})),
                response(reply("[模拟] " + texts[name])),
            ], args.demo)
            workspace = Workspace(directory)
            tools = [tool for tool in workspace.tools() if not tool.mutating]
            agent = ResponsesAgent(client, os.getenv("OPENAI_MODEL", "gpt-6-astra"),
                                   ToolRegistry(tools), max_turns=4, max_tool_calls=4,
                                   instructions=f"你是 {name}。只分析自己的资料，用中文给出简明证据。")
            result = agent.run(prompt + ("\n补充要求：" + args.prompt if args.prompt else ""))
            if result.status != "completed":
                raise RuntimeError(f"成员停止状态：{result.status}；{result.text}")
            return {"answer": result.text, "workspace": str(directory),
                    "history_items": len(result.history)}

        results = run_team(tasks, worker, Path(temporary), max_workers=2)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if any(item["status"] != "completed" for item in results.values()):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
