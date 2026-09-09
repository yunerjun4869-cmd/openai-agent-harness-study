"""任务依赖、所有权和真实多进程竞争的离线测试。"""

from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from harness.storage import TaskStore


def _claim_in_process(path, owner, queue):
    store, claimed = TaskStore(path), []
    while True:
        task = store.claim(owner)
        if task is None:
            break
        claimed.append(task["id"])
    queue.put(claimed)


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "tasks.sqlite3"
        self.store = TaskStore(self.path)

    def finish(self, task, **kwargs):
        return self.store.complete(task["id"], task["owner"], task["lease_token"], **kwargs)

    def test_dependencies_gate_claim_and_failure_blocks_descendants(self):
        self.store.create("a", "准备")
        self.store.create("b", "测试", dependencies=["a"])
        self.store.create("c", "交付", dependencies=["b"])
        task = self.store.claim("worker", now=100)
        self.assertEqual(task["id"], "a")
        self.assertIsNone(self.store.claim("other", now=100))
        self.finish(task, error="准备失败", now=101)
        self.assertEqual(self.store.get("a")["status"], "failed")
        self.assertEqual(self.store.get("b")["status"], "blocked")
        self.assertEqual(self.store.get("c")["status"], "blocked")
        self.assertIsNone(self.store.claim("other", now=102))

    def test_success_unlocks_dependency(self):
        self.store.create("a", "准备")
        self.store.create("b", "测试", dependencies=["a"])
        task = self.store.claim("worker", now=100)
        self.finish(task, result={"count": 2}, now=101)
        self.assertEqual(self.store.get("a")["result"], {"count": 2})
        self.assertEqual(self.store.claim("worker", now=102)["id"], "b")

    def test_cycle_and_missing_dependency_roll_back(self):
        self.store.create("a", "准备")
        self.store.create("b", "测试", dependencies=["a"])
        with self.assertRaises(ValueError):
            self.store.add_dependencies("a", ["b"])
        self.assertEqual(self.store.get("a")["dependencies"], [])
        with self.assertRaises(ValueError):
            self.store.create("c", "缺依赖", dependencies=["missing"])
        with self.assertRaises(KeyError):
            self.store.get("c")
        with self.assertRaises(ValueError):
            self.store.add_dependencies("a", ["a"])

    def test_owner_token_and_lease_are_all_required(self):
        self.store.create("a", "准备")
        first = self.store.claim("worker", now=100, lease_seconds=5)
        with self.assertRaises(PermissionError):
            self.store.complete("a", "intruder", first["lease_token"], now=101)
        with self.assertRaises(PermissionError):
            self.finish(first, now=105)
        second = self.store.claim("worker", now=106, lease_seconds=5)
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        with self.assertRaises(PermissionError):
            self.finish(first, now=106)
        self.assertEqual(self.finish(second, now=107)["status"], "completed")

    def test_future_tasks_wait_until_due_and_survive_reopen(self):
        self.store.create("later", "提醒", payload={"value": 1}, available_at=500)
        reopened = TaskStore(self.path)
        self.assertIsNone(reopened.claim("worker", now=499))
        self.assertEqual(reopened.claim("worker", now=500)["payload"], {"value": 1})

    def test_nonfinite_timing_is_rejected(self):
        for value in (float("nan"), float("inf"), "100"):
            with self.assertRaises(ValueError):
                self.store.create("invalid", "无效时间", available_at=value)
            with self.assertRaises(ValueError):
                self.store.claim("worker", lease_seconds=value)

    def test_threads_cannot_claim_same_task(self):
        for index in range(16):
            self.store.create(str(index), "并发任务")
        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = list(executor.map(lambda i: self.store.claim(f"worker-{i}"), range(24)))
        ids = [task["id"] for task in tasks if task]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)

    def test_processes_cannot_claim_same_task(self):
        for index in range(12):
            self.store.create(str(index), "跨进程任务")
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        workers = [context.Process(target=_claim_in_process,
                                   args=(str(self.path), f"p{i}", queue)) for i in range(3)]
        try:
            for worker in workers:
                worker.start()
            claimed = [task for _ in workers for task in queue.get(timeout=15)]
            for worker in workers:
                worker.join(timeout=15)
                self.assertEqual(worker.exitcode, 0)
            self.assertEqual(len(claimed), 12)
            self.assertEqual(len(set(claimed)), 12)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
            queue.close()
            queue.join_thread()


if __name__ == "__main__":
    unittest.main()
