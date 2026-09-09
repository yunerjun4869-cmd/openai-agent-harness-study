"""验证文件边界、真实子进程超时和真实输出上限。"""
import os
from pathlib import Path
import sys

import pytest

from harness.filesystem import Workspace


def test_traversal_absolute_paths_and_symlink_escape(tmp_path):
    root = tmp_path / "workspace"
    workspace = Workspace(root)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (root / "link").symlink_to(outside)
    for path in ("../secret.txt", str(outside), "link", ".env", ".git/config"):
        with pytest.raises(PermissionError):
            workspace.read_file(path)
        with pytest.raises(PermissionError):
            workspace.write_file(path, "changed")
    assert outside.read_text() == "secret"
    assert "link" not in workspace.list_files()["files"]


def test_atomic_write_and_explicit_read_truncation(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("sub/note.txt", "可验证")
    assert workspace.read_file("sub/note.txt")["content"] == "可验证"
    (tmp_path / "large.txt").write_bytes(b"a" * 70000)
    result = workspace.read_file("large.txt")
    assert result["truncated"] and len(result["content"]) == 65536


def test_command_is_argv_not_shell_and_filters_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    workspace = Workspace(tmp_path)
    result = workspace.run_command([sys.executable, "-c",
        "import os,sys; print(sys.argv[1]); print(os.getenv('OPENAI_API_KEY'))", "$(touch escaped)"])
    assert result["exit_code"] == 0
    assert "$(touch escaped)" in result["stdout"] and "None" in result["stdout"]
    assert not (tmp_path / "escaped").exists()


def test_timeout_and_output_bounds(tmp_path):
    workspace = Workspace(tmp_path, command_timeout=0.1)
    result = workspace.run_command([sys.executable, "-c", "import time; time.sleep(10)"])
    assert result["timed_out"] is True and result["exit_code"] != 0
    workspace.command_timeout = 5
    result = workspace.run_command([sys.executable, "-c", "print('x' * 20000)"])
    assert result["truncated"] is True and len(result["stdout"]) == 8192
