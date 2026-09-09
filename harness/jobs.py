"""有界后台执行，以及可重启的一次性定时任务。"""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Lock

from .storage import TaskStore


class BackgroundJobs:
    """限制工作线程和未完成任务数；result() 保留原异常语义。"""

    def __init__(self, max_workers=2, max_pending=8):
        if (type(max_workers) is not int or type(max_pending) is not int
                or max_workers < 1 or max_pending < max_workers):
            raise ValueError("工作线程须为正数，任务容量不得小于工作线程数")
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_pending = max_pending
        self._futures = {}
        self._lock = Lock()
        self._closed = False

    def submit(self, job_id, fn, *args, **kwargs):
        with self._lock:
            if self._closed:
                raise RuntimeError("后台任务池已经关闭")
            if job_id in self._futures:
                raise ValueError(f"任务 ID 已使用：{job_id}")
            if sum(not future.done() for future in self._futures.values()) >= self._max_pending:
                raise RuntimeError("后台任务容量已满，请先等待任务完成")
            self._futures[job_id] = self._executor.submit(fn, *args, **kwargs)
        return job_id

    def _future(self, job_id):
        with self._lock:
            return self._futures[job_id]

    def status(self, job_id):
        future = self._future(job_id)
        if future.cancelled():
            return "cancelled"
        if future.done():
            return "failed" if future.exception() is not None else "completed"
        return "running" if future.running() else "pending"

    def result(self, job_id, timeout=None):
        """超时只停止等待；Python 线程中的工作不会被强制终止。"""
        return self._future(job_id).result(timeout=timeout)

    def forget(self, job_id):
        """显式释放已完成任务的内存；历史记录不是持久化任务队列。"""
        with self._lock:
            if not self._futures[job_id].done():
                raise RuntimeError("任务尚未完成，不能移除")
            del self._futures[job_id]

    def close(self):
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PersistentScheduler:
    """一次性时间戳调度；调用 run_due 才执行，无守护线程或完整 cron。"""

    def __init__(self, path, handlers, lease_seconds=60):
        self.store = TaskStore(path)
        self.handlers = dict(handlers)
        self.lease_seconds = lease_seconds

    def schedule(self, job_id, action, payload, run_at):
        if action not in self.handlers:
            raise ValueError(f"未注册定时动作：{action}")
        return self.store.create(job_id, action, payload={"action": action, "input": payload},
                                 available_at=run_at)

    def run_due(self, owner, now=None, limit=10):
        """claim/执行/ack 不是同一事务；崩溃恢复可能重复执行，动作需幂等。"""
        if type(limit) is not int or limit < 1:
            raise ValueError("每批执行上限必须为正数")
        records = []
        for _ in range(limit):
            task = self.store.claim(owner, now=now, lease_seconds=self.lease_seconds)
            if task is None:
                break
            try:
                payload = task["payload"]
                result = self.handlers[payload["action"]](payload["input"])
                json.dumps(result, allow_nan=False)
            except Exception as exc:
                record = self.store.complete(task["id"], owner, task["lease_token"],
                                             error=f"{type(exc).__name__}: {exc}", now=now)
            else:
                record = self.store.complete(task["id"], owner, task["lease_token"],
                                             result=result, now=now)
            records.append(record)
        return records
