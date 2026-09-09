"""第五课：用小型状态约束，让计划保持可读与一致。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response


class TodoBoard:
    def __init__(self):
        self.items = []

    def update(self, items):
        if len(items) > 12:
            raise ValueError("计划最多 12 项，请拆分任务")
        if len({item["id"] for item in items}) != len(items):
            raise ValueError("任务 id 必须唯一")
        if any(not item["id"].strip() or not item["text"].strip() for item in items):
            raise ValueError("任务 id 与描述不能为空")
        if sum(item["status"] == "in_progress" for item in items) > 1:
            raise ValueError("最多一项任务处于进行中")
        self.items = [dict(item) for item in items]
        return {"items": self.items,
                "completed": sum(item["status"] == "completed" for item in items)}

    def tool(self):
        item_schema = object_schema({"id": {"type": "string"},
            "text": {"type": "string"}, "status": {"type": "string",
            "enum": ["pending", "in_progress", "completed"]}})
        return Tool("update_todos", "替换当前会话计划；同一时间最多执行一项", object_schema({
            "items": {"type": "array", "items": item_schema}}), self.update)


def main():
    args = lesson_args(__doc__)
    board = TodoBoard()
    first = [{"id": "read", "text": "理解工具循环", "status": "in_progress"},
             {"id": "explain", "text": "解释 call_id", "status": "pending"}]
    second = [{"id": "read", "text": "理解工具循环", "status": "completed"},
              {"id": "explain", "text": "解释 call_id", "status": "in_progress"}]
    run_example([board.tool()], args.prompt or
                "用计划工具安排两步：理解工具循环、解释 call_id；然后解释调用如何关联返回。", [
        response(call("update_todos", {"items": first})),
        response(call("update_todos", {"items": second}, "call_2")),
        response(reply("call_id 将模型的函数调用与执行器返回关联。当前计划仍有一项进行中。")),
    ], args)
    print("会话计划：", board.items)


if __name__ == "__main__":
    main()
