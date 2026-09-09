"""s17：模型说完成后，宿主仍运行固定验收器决定是否继续。"""
from dataclasses import asdict
from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response
from harness.filesystem import Workspace
from harness.goal import Evidence, GoalLoop


def run_checks(workspace):
    """验收代码由宿主固定，模型只能修改 result.json 等工作文件。"""
    checks, failures = 3, []
    try:
        raw = workspace.read_file("result.json")
        if raw["truncated"]:
            raise ValueError("结果文件超出读取上限")
        data = json.loads(raw["content"])
        if not isinstance(data, dict):
            raise ValueError("结果必须是 JSON 对象")
        if data.get("numbers") != [2, 3, 5]:
            failures.append("numbers 必须精确等于 [2, 3, 5]")
        if type(data.get("sum")) is not int or data["sum"] != 10:
            failures.append("sum 必须是整数 10")
        if set(data) != {"numbers", "sum"}:
            failures.append("结果只能包含 numbers 和 sum 两个字段")
    except (OSError, ValueError, PermissionError) as exc:
        failures.append(f"无法验收结果文件：{type(exc).__name__}")
    return {"exit_code": 1 if failures else 0, "checks": checks,
            "failures": failures, "target": "result.json"}


def main():
    args = lesson_args(__doc__)
    with tempfile.TemporaryDirectory(prefix="openai-s17-") as temporary:
        root = Path(temporary) if args.demo else args.workspace / "s17" / "files"
        workspace = Workspace(root)
        if args.demo:
            args.allow_write = True
        tools = workspace.tools() + [Tool("run_checks", "运行宿主固定的结果验收器",
                                         object_schema({}), lambda: run_checks(workspace))]
        feedback = []

        def attempt(round_number):
            value = 0 if round_number == 1 else 10
            scripted = [
                response(call("write_file", {"path": "result.json", "content": json.dumps(
                    {"numbers": [2, 3, 5], "sum": value})}, f"goal_{round_number}")),
                response(reply("[模拟] 我已经完成了任务。")),
            ]
            prompt = ("生成 result.json，仅含 numbers=[2,3,5] 和它们的整数 sum。"
                      "使用工具检查；你声称完成后宿主仍会独立验收。")
            if feedback:
                prompt += "\n上次宿主验收：" + json.dumps(feedback[-1], ensure_ascii=False)
            if args.prompt:
                prompt += "\n补充要求：" + args.prompt
            try:
                result = run_example(tools, prompt, scripted, args)
            except SystemExit as exc:
                # 单章 CLI 的退出不能跳过外层目标状态报告。
                raise RuntimeError(f"本轮 Agent 提前退出，退出码：{exc.code}") from exc
            if result.status != "completed":
                raise RuntimeError("本轮 Agent 未完成：" + result.status)
            return result.text  # GoalLoop 从不把这段文字用作成功证据。

        def verify():
            report = run_checks(workspace)
            feedback.append(report)
            print("独立工具验收：", json.dumps(report, ensure_ascii=False))
            return Evidence(report["exit_code"] == 0 and report["checks"] == 3,
                            "run_checks:host-defined", report)

        result = GoalLoop(max_rounds=3).run(attempt, verify)
        print("目标结果：", json.dumps(asdict(result), ensure_ascii=False, indent=2))
        if result.status != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
