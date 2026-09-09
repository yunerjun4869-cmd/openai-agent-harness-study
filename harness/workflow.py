"""输入与版本绑定的步骤日志；提交前崩溃会重放步骤，副作用需幂等。"""

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class WorkflowJournal:
    """租约防止正常情况下并发运行；长期步骤须自行保证短于租约。"""

    def __init__(self, path, lease_seconds=60):
        if (str(path) == ":memory:" or type(lease_seconds) not in (int, float)
                or not math.isfinite(lease_seconds) or lease_seconds <= 0):
            raise ValueError("需要数据库文件和正数租约时长")
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lease_seconds = lease_seconds
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY, version TEXT NOT NULL, fingerprint TEXT NOT NULL,
                signature TEXT NOT NULL, status TEXT NOT NULL, owner TEXT, lease_until REAL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_steps (
                workflow_id TEXT NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL,
                status TEXT NOT NULL, result TEXT, error TEXT,
                PRIMARY KEY(workflow_id,name))""")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def inspect(self, workflow_id):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if row is None:
                raise KeyError(f"工作流不存在：{workflow_id}")
            state = dict(row)
            state["steps"] = [dict(step) for step in db.execute(
                "SELECT * FROM workflow_steps WHERE workflow_id=? ORDER BY position", (workflow_id,))]
            for step in state["steps"]:
                if step["result"] is not None:
                    step["result"] = json.loads(step["result"])
            return state

    def _claim(self, workflow_id, version, inputs, names):
        fingerprint = hashlib.sha256(_encode(inputs).encode()).hexdigest()
        signature, owner, now = _encode(names), uuid.uuid4().hex, time.time()
        with self._transaction() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if row is None:
                db.execute("INSERT INTO workflows VALUES (?,?,?,?,'pending',NULL,NULL)",
                           (workflow_id, version, fingerprint, signature))
                db.executemany("INSERT INTO workflow_steps VALUES (?,?,?,'pending',NULL,NULL)",
                               [(workflow_id, name, i) for i, name in enumerate(names)])
            else:
                if (row["version"], row["fingerprint"], row["signature"]) != (
                        version, fingerprint, signature):
                    raise ValueError("工作流版本、输入或步骤序列已改变，请使用新的工作流 ID")
                if row["owner"] is not None and row["lease_until"] > now:
                    raise RuntimeError("工作流已有持有有效租约的执行者")
            db.execute("UPDATE workflows SET status='running',owner=?,lease_until=? WHERE id=?",
                       (owner, now + self.lease_seconds, workflow_id))
        return owner

    def _assert_owner(self, db, workflow_id, owner):
        row = db.execute("SELECT owner,lease_until FROM workflows WHERE id=?", (workflow_id,)).fetchone()
        if row["owner"] != owner or row["lease_until"] <= time.time():
            raise PermissionError("工作流租约已失效，拒绝提交旧执行者的结果")

    def run(self, workflow_id, version, inputs, steps):
        """fn 接收 {'inputs': 输入, 'results': 已完成结果}，返回 JSON 可序列化值。"""
        steps = list(steps)
        inputs = deepcopy(inputs)
        names = [name for name, _ in steps]
        if (not workflow_id or not isinstance(version, str) or not version
                or not names or len(names) != len(set(names))
                or any(not isinstance(name, str) or not name for name in names)
                or any(not callable(fn) for _, fn in steps)):
            raise ValueError("工作流需要 ID、字符串版本和名称唯一的可执行步骤")
        owner = self._claim(workflow_id, version, inputs, names)
        results, active_name = {}, None
        try:
            for name, fn in steps:
                active_name = name
                with self._transaction() as db:
                    self._assert_owner(db, workflow_id, owner)
                    row = db.execute("SELECT * FROM workflow_steps WHERE workflow_id=? AND name=?",
                                     (workflow_id, name)).fetchone()
                    if row["status"] == "completed":
                        results[name] = json.loads(row["result"])
                        continue
                    db.execute("UPDATE workflows SET lease_until=? WHERE id=?",
                               (time.time() + self.lease_seconds, workflow_id))
                    db.execute("""UPDATE workflow_steps SET status='running',error=NULL
                        WHERE workflow_id=? AND name=?""", (workflow_id, name))
                result = fn({"inputs": deepcopy(inputs), "results": deepcopy(results)})
                encoded = _encode(result)
                with self._transaction() as db:
                    self._assert_owner(db, workflow_id, owner)
                    db.execute("""UPDATE workflow_steps SET status='completed',result=?,error=NULL
                        WHERE workflow_id=? AND name=?""", (encoded, workflow_id, name))
                results[name] = json.loads(encoded)
            with self._transaction() as db:
                self._assert_owner(db, workflow_id, owner)
                db.execute("UPDATE workflows SET status='completed',owner=NULL,lease_until=NULL WHERE id=?",
                           (workflow_id,))
            return results
        except BaseException as exc:
            with self._transaction() as db:
                row = db.execute("SELECT owner FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                if row["owner"] == owner:
                    db.execute("""UPDATE workflow_steps SET status='failed',error=?
                        WHERE workflow_id=? AND name=? AND status!='completed'""",
                               (f"{type(exc).__name__}: {exc}", workflow_id, active_name))
                    db.execute("UPDATE workflows SET status='failed',owner=NULL,lease_until=NULL WHERE id=?",
                               (workflow_id,))
            raise
