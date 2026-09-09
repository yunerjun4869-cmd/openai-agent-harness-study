"""按需知识与带来源的记忆；内容始终是数据，不自动升级为系统指令。"""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class SkillLibrary:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def list_skills(self) -> list[dict]:
        return [{"name": path.stem, "bytes": path.stat().st_size}
                for path in sorted(self.root.glob("*.md"))
                if path.resolve().is_relative_to(self.root) and path.is_file()]

    def load(self, name: str) -> dict:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("技能名必须是单个文件名，不允许路径")
        path = (self.root / f"{name}.md").resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("技能文件超出技能目录")
        if path.stat().st_size > 20000:
            raise ValueError("技能文件过大，请拆分后按需加载")
        return {"name": name, "source": str(path), "trusted": False,
                "content": path.read_text(encoding="utf-8")}


class MemoryStore:
    """SQLite 存储审阅状态；即使已审阅也不能覆盖系统与用户当前指令。"""
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL,
            created_at TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0)""")
        self.connection.commit()

    def save(self, text: str, source: str) -> dict:
        if not text.strip() or not source.strip():
            raise ValueError("记忆文本与来源不能为空")
        if len(text) > 4000 or len(source) > 1000:
            raise ValueError("记忆或来源过长")
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute(
            "INSERT INTO memories(text,source,created_at) VALUES(?,?,?)",
            (text, source, created_at))
        self.connection.commit()
        return {"id": cursor.lastrowid, "source": source, "reviewed": False}

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not 1 <= limit <= 20:
            raise ValueError("检索条数必须在 1 到 20 之间")
        # 用 instr 做文字子串查找；SQL 参数绑定避免查询字符串成为 SQL。
        rows = self.connection.execute(
            "SELECT id,text,source,created_at,reviewed FROM memories "
            "WHERE instr(lower(text),lower(?)) > 0 ORDER BY id DESC LIMIT ?",
            (query, limit)).fetchall()
        return [{"id": r[0], "text": r[1], "source": r[2], "created_at": r[3],
                 "reviewed": bool(r[4]), "trusted_as_instruction": False} for r in rows]

    def close(self):
        self.connection.close()
