"""工作目录约束与有界命令输出；这是宿主工具策略，不是操作系统安全沙箱。"""
import os
from pathlib import Path
import signal
import subprocess
import tempfile

from .tools import Tool, object_schema


class Workspace:
    def __init__(self, root, command_timeout=10):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not 0 < command_timeout <= 60:
            raise ValueError("命令超时必须在 0 到 60 秒之间")
        self.command_timeout = command_timeout

    def _path(self, path):
        candidate = Path(path)
        if candidate.is_absolute():
            raise PermissionError("请使用工作目录内的相对路径")
        result = (self.root / candidate).resolve()
        if not result.is_relative_to(self.root):
            raise PermissionError("路径或符号链接越过工作目录")
        parts = result.relative_to(self.root).parts
        if any(p in (".git", ".ssh", ".venv") or p.startswith(".env") for p in parts):
            raise PermissionError("此路径包含凭证或内部目录，不向模型开放")
        return result

    def read_file(self, path):
        target = self._path(path)
        with target.open("rb") as stream:
            raw = stream.read(65537)
        return {"path": path, "content": raw[:65536].decode("utf-8", errors="replace"),
                "truncated": len(raw) > 65536}

    def write_file(self, path, content):
        if len(content.encode("utf-8")) > 65536:
            raise ValueError("单次写入内容不能超过 64 KiB")
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # 同目录临时文件 + replace，防止读到半写状态；非对抗性目录下的教学实现。
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return {"path": path, "bytes": len(content.encode("utf-8"))}

    def list_files(self):
        files = []
        # 不递归 symlink 目录；限制最多返回 200 条。
        for current, directories, names in os.walk(self.root, followlinks=False):
            directories[:] = sorted(d for d in directories
                                    if not d.startswith(".") and d != "node_modules")
            for name in sorted(names):
                relative = (Path(current) / name).relative_to(self.root).as_posix()
                try:
                    self._path(relative)
                except PermissionError:
                    continue
                files.append(relative)
                if len(files) >= 200:
                    return {"files": files, "truncated": True}
        return {"files": files, "truncated": False}

    def run_command(self, argv):
        if not argv or len(argv) > 64 or any(not isinstance(v, str) or not v for v in argv):
            raise ValueError("argv 必须是非空字符串数组，最多 64 项")
        environment = {key: value for key, value in os.environ.items()
                       if key in ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")}
        timed_out = False
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(argv, cwd=self.root, shell=False,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       env=environment, start_new_session=(os.name == "posix"))
            try:
                process.wait(timeout=self.command_timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                elif process.poll() is None:
                    process.kill()
                process.wait()
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(8193), stderr.read(8193)
        return {"exit_code": process.returncode, "stdout": out[:8192].decode("utf-8", "replace"),
                "stderr": err[:8192].decode("utf-8", "replace"), "timed_out": timed_out,
                "truncated": len(out) > 8192 or len(err) > 8192}

    def tools(self, include_command=False):
        tools = [
            Tool("list_files", "列出工作目录内最多 200 个文件", object_schema({}), self.list_files),
            Tool("read_file", "读取工作目录内文本文件，返回是否截断",
                 object_schema({"path": {"type": "string"}}), self.read_file),
            Tool("write_file", "在工作目录内写入文本文件，需要宿主授权",
                 object_schema({"path": {"type": "string"}, "content": {"type": "string"}}),
                 self.write_file, mutating=True),
        ]
        if include_command:
            tools.append(Tool("run_command", "执行已授权的程序参数数组，10 秒超时；没有 Shell 展开",
                              object_schema({"argv": {"type": "array", "items": {"type": "string"}}}),
                              self.run_command, mutating=True))
        return tools
