"""内层 CLI 提前退出仍应产生可检查的外层目标失败状态。"""
from types import SimpleNamespace

import pytest

from s17_goal_loop import code as lesson


def test_child_cli_exit_is_reported_as_failed_goal(monkeypatch, tmp_path, capsys):
    args = SimpleNamespace(demo=True, workspace=tmp_path, allow_write=False, prompt=None)
    monkeypatch.setattr(lesson, "lesson_args", lambda _: args)

    def failed_agent(*args, **kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(lesson, "run_example", failed_agent)
    with pytest.raises(SystemExit) as error:
        lesson.main()
    assert error.value.code == 1
    output = capsys.readouterr().out
    assert '"status": "failed"' in output
    assert '"evidence": []' in output
    assert "本轮 Agent 提前退出" in output
