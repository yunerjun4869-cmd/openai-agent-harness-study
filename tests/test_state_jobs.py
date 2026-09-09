"""后台容量、原异常和定时任务重启恢复的离线测试。"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
import tempfile
from threading import Event, Lock
import unittest

from harness.jobs import BackgroundJobs, PersistentScheduler


def _fail(_=None):
    raise ValueError("预期的工作失败")


class BackgroundTests(unittest.TestCase):
    def test_capacity_timeout_result_and_release(self):
        started, release = Event(), Event()

        def slow():
            started.set()
            release.wait(5)
            return 42

        with BackgroundJobs(max_workers=1, max_pending=1) as jobs:
            jobs.submit("slow", slow)
            self.assertTrue(started.wait(5))
            try:
                self.assertEqual(jobs.status("slow"), "running")
                with self.assertRaises(RuntimeError):
                    jobs.submit("full", lambda: None)
                with self.assertRaises(TimeoutError):
                    jobs.result("slow", timeout=0.001)
                with self.assertRaises(RuntimeError):
                    jobs.forget("slow")
            finally:
                release.set()
            self.assertEqual(jobs.result("slow", timeout=5), 42)
            self.assertEqual(jobs.status("slow"), "completed")
            jobs.forget("slow")
            jobs.submit("next", lambda: 7)
            self.assertEqual(jobs.result("next", timeout=5), 7)
        with self.assertRaises(RuntimeError):
            jobs.submit("closed", lambda: None)

    def test_original_exception_is_propagated(self):
        with BackgroundJobs() as jobs:
            jobs.submit("bad", _fail)
            with self.assertRaisesRegex(ValueError, "预期的工作失败"):
                jobs.result("bad", timeout=5)
            self.assertEqual(jobs.status("bad"), "failed")


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "schedule.sqlite3"

    def test_due_reopen_and_expired_claim_recovery(self):
        calls = []
        handlers = {"record": lambda payload: calls.append(payload) or {"saved": payload}}
        scheduler = PersistentScheduler(self.path, handlers)
        scheduler.schedule("once", "record", 9, run_at=100)
        self.assertEqual(scheduler.run_due("first", now=99), [])
        abandoned = scheduler.store.claim("crashed", now=100, lease_seconds=5)
        self.assertIsNotNone(abandoned)
        resumed = PersistentScheduler(self.path, handlers)
        self.assertEqual(resumed.run_due("second", now=104), [])
        records = resumed.run_due("second", now=106)
        self.assertEqual(records[0]["status"], "completed")
        self.assertEqual(records[0]["result"], {"saved": 9})
        self.assertEqual(calls, [9])
        self.assertEqual(resumed.run_due("second", now=107), [])

    def test_handler_failure_remains_failed(self):
        scheduler = PersistentScheduler(self.path, {"fail": _fail})
        scheduler.schedule("bad", "fail", {}, run_at=0)
        record = scheduler.run_due("worker", now=100)[0]
        self.assertEqual(record["status"], "failed")
        self.assertIn("ValueError", record["error"])
        self.assertEqual(scheduler.run_due("worker", now=200), [])

    def test_unserializable_result_is_recorded_as_failure(self):
        scheduler = PersistentScheduler(self.path, {"bad_result": lambda _: object()})
        scheduler.schedule("bad", "bad_result", {}, run_at=0)
        record = scheduler.run_due("worker", now=100)[0]
        self.assertEqual(record["status"], "failed")
        self.assertIn("TypeError", record["error"])

    def test_competing_schedulers_execute_each_due_task_once_while_lease_valid(self):
        calls, lock = [], Lock()

        def record(payload):
            with lock:
                calls.append(payload)
            return payload

        handlers = {"record": record}
        first, second = (PersistentScheduler(self.path, handlers) for _ in range(2))
        for index in range(8):
            first.schedule(str(index), "record", index, run_at=10)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(s.run_due, f"w{i}", now=100)
                       for i, s in enumerate((first, second))]
            records = [r for future in futures for r in future.result(timeout=10)]
        self.assertEqual(sorted(calls), list(range(8)))
        self.assertEqual(len(records), 8)


if __name__ == "__main__":
    unittest.main()
