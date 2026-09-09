"""工作流恢复、版本隔离以及提交前真实进程崩溃测试。"""

from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from harness.workflow import WorkflowJournal


def _crash_workflow(path, effects_path):
    def first(context):
        with open(effects_path, "a", encoding="utf-8") as stream:
            stream.write("准备完成\n")
        return {"value": context["inputs"]["value"]}

    def second(_):
        with open(effects_path, "a", encoding="utf-8") as stream:
            stream.write("外部副作用已发生，尚未提交日志\n")
        os._exit(7)

    journal = WorkflowJournal(path, lease_seconds=1)
    with patch("harness.workflow.time.time", return_value=100):
        journal.run("crash", "v1", {"value": 3}, [("first", first), ("second", second)])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "workflow.sqlite3"
        self.journal = WorkflowJournal(self.path)

    def test_completed_steps_skip_and_failed_steps_retry(self):
        counts = {"first": 0, "second": 0}

        def first(context):
            counts["first"] += 1
            return context["inputs"]["value"] * 2

        def second(context):
            counts["second"] += 1
            if counts["second"] == 1:
                raise ValueError("临时失败")
            return context["results"]["first"] + 1

        steps = [("first", first), ("second", second)]
        with self.assertRaisesRegex(ValueError, "临时失败"):
            self.journal.run("demo", "v1", {"value": 3}, steps)
        state = self.journal.inspect("demo")
        self.assertEqual(state["status"], "failed")
        self.assertEqual([s["status"] for s in state["steps"]], ["completed", "failed"])
        reopened = WorkflowJournal(self.path)
        result = reopened.run("demo", "v1", {"value": 3}, steps)
        self.assertEqual(result, {"first": 6, "second": 7})
        self.assertEqual(counts, {"first": 1, "second": 2})
        self.assertEqual(reopened.run("demo", "v1", {"value": 3}, steps), result)
        self.assertEqual(counts, {"first": 1, "second": 2})

    def test_input_version_and_step_order_cannot_reuse_old_results(self):
        steps = [("a", lambda _: 1), ("b", lambda _: 2)]
        self.journal.run("demo", "v1", {"a": 1, "b": 2}, steps)
        self.assertEqual(self.journal.run("demo", "v1", {"b": 2, "a": 1}, steps), {"a": 1, "b": 2})
        for version, inputs, altered_steps in [
            ("v2", {"a": 1, "b": 2}, steps),
            ("v1", {"a": 9, "b": 2}, steps),
            ("v1", {"a": 1, "b": 2}, list(reversed(steps))),
        ]:
            with self.assertRaises(ValueError):
                self.journal.run("demo", version, inputs, altered_steps)

    def test_live_runner_blocks_second_runner(self):
        started, release = Event(), Event()

        def wait(_):
            started.set()
            release.wait(5)
            return "完成"

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.journal.run, "same", "v1", {}, [("wait", wait)])
            self.assertTrue(started.wait(5))
            try:
                with self.assertRaisesRegex(RuntimeError, "有效租约"):
                    WorkflowJournal(self.path).run("same", "v1", {}, [("wait", wait)])
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5), {"wait": "完成"})

    def test_expired_runner_cannot_commit_step(self):
        now = [100]

        def too_slow(_):
            now[0] = 102
            return "不能确认成功"

        journal = WorkflowJournal(self.path, lease_seconds=1)
        with patch("harness.workflow.time.time", side_effect=lambda: now[0]):
            with self.assertRaises(PermissionError):
                journal.run("slow", "v1", {}, [("slow", too_slow)])
        self.assertEqual(journal.inspect("slow")["steps"][0]["status"], "failed")

    def test_crash_replays_uncommitted_step_but_preserves_completed_step(self):
        effects_path = Path(self.temp.name) / "effects.txt"
        context = multiprocessing.get_context("spawn")
        worker = context.Process(target=_crash_workflow, args=(str(self.path), str(effects_path)))
        worker.start()
        worker.join(timeout=15)
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        self.assertEqual(worker.exitcode, 7)
        self.assertEqual(self.journal.inspect("crash")["status"], "running")

        def never_repeat(_):
            self.fail("已成功的第一步不应重跑")

        def resume(context):
            with effects_path.open("a", encoding="utf-8") as stream:
                stream.write("重放第二步，需要业务幂等\n")
            return context["results"]["first"]["value"] + 1

        with patch("harness.workflow.time.time", return_value=102):
            result = self.journal.run("crash", "v1", {"value": 3},
                                      [("first", never_repeat), ("second", resume)])
        self.assertEqual(result["second"], 4)
        self.assertEqual(len(effects_path.read_text(encoding="utf-8").splitlines()), 3)
        self.assertEqual(self.journal.inspect("crash")["status"], "completed")


if __name__ == "__main__":
    unittest.main()
