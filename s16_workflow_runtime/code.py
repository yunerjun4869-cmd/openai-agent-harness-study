"""s16：确定步骤图、真实模型子步骤结果与失败后的 journal 恢复。"""
from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response
from harness.workflow import WorkflowJournal


class DemoInterruption(RuntimeError):
    pass


def main():
    args = lesson_args(__doc__)
    with tempfile.TemporaryDirectory(prefix="openai-s16-") as temporary:
        root = Path(temporary) if args.demo else args.workspace / "s16"
        root.mkdir(parents=True, exist_ok=True)
        database = root / "workflow.sqlite3"
        workflow_id, version = "learning-report", "1"
        inputs = {"topic": args.prompt or "解释 Responses API 的 call_id 如何配对工具结果。"}
        counters = {"prepare": 0, "analyze": 0, "publish": 0}

        def prepare(context):
            counters["prepare"] += 1
            topic = context["inputs"]["topic"]
            return {"topic": topic, "characters": len(topic)}

        def analyze(context):
            counters["analyze"] += 1
            prepared = context["results"]["prepare"]
            tools = [Tool("read_topic", "读取已固定的工作流输入", object_schema({}),
                          lambda: prepared)]
            result = run_example(tools, "读取主题并写出三条学习要点。", [
                response(call("read_topic", {}, "workflow_1")),
                response(reply("[模拟] 1. 保留全部 output。2. 使用 call_id 配对。3. 将 function_call_output 发回模型。")),
            ], args)
            if result.status != "completed":
                raise RuntimeError("模型子步骤没有完成：" + result.status)
            return {"text": result.text, "usage": result.usage}

        def publish(context):
            counters["publish"] += 1
            if args.demo and counters["publish"] == 1:
                raise DemoInterruption("[演示故障] 模型分析完成后，发布步骤第一次失败")
            path = root / "report.md"
            content = "# 工作流学习报告\n\n" + context["results"]["analyze"]["text"] + "\n"
            # 固定路径覆盖写是本例的幂等动作；不等同于任意外部副作用恰好一次。
            path.write_text(content, encoding="utf-8")
            return {"path": str(path), "characters": len(content)}

        steps = [("prepare", prepare), ("analyze", analyze), ("publish", publish)]
        journal = WorkflowJournal(database)
        try:
            results = journal.run(workflow_id, version, inputs, steps)
        except DemoInterruption as exc:
            print(exc)
            print("故障后步骤状态：", [(s["name"], s["status"]) for s in journal.inspect(workflow_id)["steps"]])
            print("重新打开 journal，继续相同输入与版本的工作流。")
            results = WorkflowJournal(database).run(workflow_id, version, inputs, steps)
        print("各步骤实际调用次数：", counters)
        print("步骤结果：", json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
