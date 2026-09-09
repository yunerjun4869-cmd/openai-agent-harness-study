"""第四课：围绕工具执行加审计与策略钩子。"""
from pathlib import Path
import json
import os
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, make_client
from harness.core import ResponsesAgent, Tool, ToolRegistry, object_schema
from harness.fakes import call, reply, response


class AuditHook:
    def __init__(self):
        self.started = {}
        self.events = []

    def __call__(self, event, payload):
        name = payload["name"]
        record = {"event": event, "tool": name}
        if event == "before":
            self.started[name] = monotonic()
        if event in {"after", "error"} and name in self.started:
            record["elapsed_ms"] = round((monotonic() - self.started.pop(name)) * 1000, 2)
        self.events.append(record)
        print("审计：", json.dumps(record, ensure_ascii=False))


def main():
    args = lesson_args(__doc__)
    audit = AuditHook()
    tool = Tool("count_words", "按空格统计文本中的词数", object_schema({
        "text": {"type": "string"}}), lambda text: {"words": len(text.split())})
    client = make_client([
        response(call("count_words", {"text": "tools need observability"})),
        response(reply("工具返回 3 个词；执行前后均留下审计事件。")),
    ], args.demo)
    registry = ToolRegistry([tool], hooks=[audit])
    agent = ResponsesAgent(client, os.getenv("OPENAI_MODEL", "gpt-6-astra"), registry)
    result = agent.run(args.prompt or "调用工具统计 tools need observability 的词数。")
    print(f"状态：{result.status}\n{result.text}")
    print(f"审计事件数：{len(audit.events)}；日志不记录原始文本。")
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
