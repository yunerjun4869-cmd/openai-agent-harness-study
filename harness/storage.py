"""SQLite 任务图：事务认领、带租约的所有权与依赖失败传播。"""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid


def _finite_number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label}必须是有限数字")
    return value


class TaskStore:
    """每次操作新建连接，适用于线程与本机多进程；不支持 :memory:。"""

    def __init__(self, path):
        if str(path) == ":memory:":
            raise ValueError("请使用数据库文件，以便多个连接共享状态")
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
                payload TEXT NOT NULL, available_at REAL NOT NULL, owner TEXT,
                lease_token TEXT, lease_until REAL, result TEXT, error TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS task_deps (
                task_id TEXT REFERENCES tasks(id), depends_on TEXT REFERENCES tasks(id),
                PRIMARY KEY(task_id, depends_on))""")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _record(self, db, task_id):
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"任务不存在：{task_id}")
        task = dict(row)
        for key in ("payload", "result"):
            task[key] = json.loads(task[key]) if task[key] is not None else None
        task["dependencies"] = [row[0] for row in db.execute(
            "SELECT depends_on FROM task_deps WHERE task_id=? ORDER BY depends_on",
            (task_id,))]
        return task

    def _add_dependencies(self, db, task_id, dependencies):
        for dependency in set(dependencies):
            if db.execute("SELECT 1 FROM tasks WHERE id=?", (dependency,)).fetchone() is None:
                raise ValueError(f"依赖任务不存在：{dependency}")
            db.execute("INSERT OR IGNORE INTO task_deps VALUES (?,?)", (task_id, dependency))
        cycle = db.execute("""WITH RECURSIVE ancestors(id) AS (
            SELECT depends_on FROM task_deps WHERE task_id=? UNION
            SELECT d.depends_on FROM task_deps d JOIN ancestors a ON d.task_id=a.id)
            SELECT 1 FROM ancestors WHERE id=? LIMIT 1""", (task_id, task_id)).fetchone()
        if cycle:
            raise ValueError("任务依赖不能形成循环")
        self._block_dependents(db)

    @staticmethod
    def _block_dependents(db):
        db.execute("""WITH RECURSIVE unavailable(id) AS (
            SELECT id FROM tasks WHERE status IN ('failed','blocked') UNION
            SELECT d.task_id FROM task_deps d JOIN unavailable u ON d.depends_on=u.id)
            UPDATE tasks SET status='blocked', error='依赖任务失败'
            WHERE status='pending' AND id IN (SELECT id FROM unavailable)""")

    def create(self, task_id, title, dependencies=(), payload=None, available_at=0):
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("任务 ID 不能为空")
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        available_at = _finite_number(available_at, "可执行时间")
        with self._transaction() as db:
            db.execute("""INSERT INTO tasks(id,title,status,payload,available_at)
                VALUES (?,?,'pending',?,?)""", (task_id, title, encoded, available_at))
            self._add_dependencies(db, task_id, dependencies)
            return self._record(db, task_id)

    def add_dependencies(self, task_id, dependencies):
        with self._transaction() as db:
            if self._record(db, task_id)["status"] != "pending":
                raise ValueError("只能修改尚未执行任务的依赖")
            self._add_dependencies(db, task_id, dependencies)
            return self._record(db, task_id)

    def get(self, task_id):
        with self._transaction() as db:
            return self._record(db, task_id)

    def list(self):
        with self._transaction() as db:
            return [self._record(db, row[0]) for row in db.execute("SELECT id FROM tasks ORDER BY id")]

    def claim(self, owner, now=None, lease_seconds=60):
        lease_seconds = _finite_number(lease_seconds, "租约时长")
        if not isinstance(owner, str) or not owner.strip() or lease_seconds <= 0:
            raise ValueError("需要非空 owner 和正数租约时长")
        now = time.time() if now is None else _finite_number(now, "当前时间")
        with self._transaction() as db:
            db.execute("""UPDATE tasks SET status='pending',owner=NULL,lease_token=NULL,
                lease_until=NULL WHERE status='running' AND lease_until<=?""", (now,))
            self._block_dependents(db)
            row = db.execute("""SELECT id FROM tasks t WHERE status='pending'
                AND available_at<=? AND NOT EXISTS (
                    SELECT 1 FROM task_deps d JOIN tasks parent ON d.depends_on=parent.id
                    WHERE d.task_id=t.id AND parent.status!='completed')
                ORDER BY available_at,id LIMIT 1""", (now,)).fetchone()
            if row is None:
                return None
            db.execute("""UPDATE tasks SET status='running',owner=?,lease_token=?,lease_until=?
                WHERE id=?""", (owner, uuid.uuid4().hex, now + lease_seconds, row[0]))
            return self._record(db, row[0])

    def complete(self, task_id, owner, lease_token, result=None, error=None, now=None):
        """令牌隔离旧执行者；租约过期后不能确认，外部副作用仍须自行幂等。"""
        now = time.time() if now is None else _finite_number(now, "当前时间")
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        with self._transaction() as db:
            task = self._record(db, task_id)
            if (task["status"] != "running" or task["owner"] != owner
                    or task["lease_token"] != lease_token or task["lease_until"] <= now):
                raise PermissionError("任务不属于当前有效租约，拒绝确认")
            status = "failed" if error is not None else "completed"
            db.execute("UPDATE tasks SET status=?,result=?,error=?,lease_until=NULL WHERE id=?",
                       (status, encoded, str(error) if error is not None else None, task_id))
            self._block_dependents(db)
            return self._record(db, task_id)
