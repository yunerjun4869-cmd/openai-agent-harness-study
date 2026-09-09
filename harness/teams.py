"""教学用有界 Agent 团队：隔离会话和目录，但不构成系统沙箱。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
from typing import Callable


def run_team(tasks: dict[str, str], worker: Callable, workspace: Path,
             max_workers: int = 2, max_tasks: int = 8) -> dict:
    """worker(name, prompt, directory) 必须为每项任务构建独立 Agent 历史。"""
    if not 1 <= max_workers <= 4 or len(tasks) > max_tasks:
        raise ValueError("团队并发必须为 1–4，任务数不能超过上限")
    if any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", name) for name in tasks):
        raise ValueError("成员名仅允许字母、数字、下划线和连字符")
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    directories = {}
    for name in tasks:
        directory = root / name
        if directory.is_symlink():
            raise ValueError("成员工作目录不能是符号链接")
        directory.mkdir(exist_ok=True)
        if not directory.resolve().is_relative_to(root):
            raise ValueError("成员工作目录越界")
        directories[name] = directory
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(worker, name, prompt, directories[name]): name
                   for name, prompt in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = {"status": "completed", "result": future.result()}
            except Exception as exc:
                results[name] = {"status": "failed", "error": str(exc)}
    return {name: results[name] for name in tasks}
