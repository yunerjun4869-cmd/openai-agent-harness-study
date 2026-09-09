"""s12：持久化到期时间、白名单动作与可重启的调度器。"""
from pathlib import Path
import json
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response
from harness.jobs import PersistentScheduler


def main():
    args = lesson_args(__doc__)
    with tempfile.TemporaryDirectory(prefix="openai-s12-") as temporary:
        root = Path(temporary) if args.demo else args.workspace / "s12"
        root.mkdir(parents=True, exist_ok=True)
        database = root / "scheduler.sqlite3"
        handlers = {"format_note": lambda payload: {"formatted": payload["text"].strip().upper()}}
        scheduler = PersistentScheduler(database, handlers)
        if args.demo:
            args.allow_write = True

        def schedule(job_id, text, delay_seconds):
            if not 0 <= delay_seconds <= 86400:
                raise ValueError("本章仅接受一天以内的延迟")
            scheduler.schedule(job_id, "format_note", {"text": text}, time.time() + delay_seconds)
            return scheduler.store.get(job_id)

        tools = [
            Tool("schedule_note", "安排本地文本格式化；延迟 0 表示立即到期", object_schema({
                "job_id": {"type": "string"}, "text": {"type": "string"},
                "delay_seconds": {"type": "integer"}}), schedule, mutating=True),
            Tool("scheduler_run_due", "执行当前已经到期的任务，不等待未来任务", object_schema({}),
                 lambda: {"executed": scheduler.run_due("course-worker")}, mutating=True),
            Tool("scheduler_list", "查看已持久化的计划和结果", object_schema({}),
                 lambda: {"jobs": scheduler.store.list()}),
        ]
        scripted = [
            response(call("schedule_note", {"job_id": "note-1", "text": "hello scheduler", "delay_seconds": 0})),
            response(call("scheduler_run_due", {}, "scheduler_2")),
            response(call("scheduler_list", {}, "scheduler_3")),
            response(reply("[模拟] note-1 到期后执行了一次；调度状态和结果保存在 SQLite。")),
        ]
        run_example(tools, args.prompt or "安排一个立即到期的 note-1 文本格式化任务，执行到期任务并查询结果。已存在就读取状态。",
                    scripted, args)
        reopened = PersistentScheduler(database, handlers)
        print("重新打开数据库后的状态：")
        print(json.dumps(reopened.store.list(), ensure_ascii=False, indent=2))
        if args.demo:
            print("重启后再次扫描，重复执行数：", len(reopened.run_due("restarted-worker")))


if __name__ == "__main__":
    main()
