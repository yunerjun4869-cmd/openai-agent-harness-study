"""s10：SQLite 依赖图、原子认领和带租约的完成操作。"""
from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response
from harness.storage import TaskStore


def task_tools(store):
    claimed = {}

    def claim_task():
        task = store.claim("learner")
        if task:
            claimed[task["id"]] = task
        return {"task": task}

    def complete_task(task_id, summary):
        task = claimed.get(task_id)
        if not task:
            raise ValueError("当前执行者未认领该任务")
        result = store.complete(task_id, "learner", task["lease_token"], summary)
        claimed.pop(task_id, None)
        return result

    return [
        Tool("task_create", "创建任务及其已存在的依赖", object_schema({
            "task_id": {"type": "string"}, "title": {"type": "string"},
            "dependencies": {"type": "array", "items": {"type": "string"}}}),
             store.create, mutating=True),
        Tool("task_claim", "原子认领一个依赖已完成的任务", object_schema({}),
             claim_task, mutating=True),
        Tool("task_complete", "完成当前执行者已认领的任务", object_schema({
            "task_id": {"type": "string"}, "summary": {"type": "string"}}),
             complete_task, mutating=True),
        Tool("task_list", "查看持久化任务状态", object_schema({}),
             lambda: {"tasks": store.list()}),
    ]


def main():
    args = lesson_args(__doc__)
    with tempfile.TemporaryDirectory(prefix="openai-s10-") as temporary:
        root = Path(temporary) if args.demo else args.workspace / "s10"
        root.mkdir(parents=True, exist_ok=True)
        store = TaskStore(root / "tasks.sqlite3")
        if args.demo:
            args.allow_write = True
        scripted = [
            response(call("task_create", {"task_id": "read", "title": "阅读需求", "dependencies": []}, "task_1")),
            response(call("task_create", {"task_id": "test", "title": "验收方案", "dependencies": ["read"]}, "task_2")),
            response(call("task_claim", {}, "task_3")),
            response(call("task_complete", {"task_id": "read", "summary": "明确验收目标"}, "task_4")),
            response(call("task_claim", {}, "task_5")),
            response(call("task_complete", {"task_id": "test", "summary": "方案已检查"}, "task_6")),
            response(call("task_list", {}, "task_7")),
            response(reply("[模拟] read 完成后 test 才能被认领；任务状态已写入 SQLite。")),
        ]
        run_example(task_tools(store), args.prompt or "创建 read 和依赖它的 test 两个任务，按顺序认领、完成，最后查询状态。",
                    scripted, args)
        print(json.dumps(store.list(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
