"""第二课：工具目录、文件读取与多步函数调用。"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.fakes import call, reply, response
from harness.filesystem import Workspace


def run(args, root):
    workspace = Workspace(root)
    run_example(workspace.tools(), args.prompt or
                "先列出工作目录文件，再读取一个文本文件并概括；不要修改文件。", [
        response(call("list_files", {})),
        response(call("read_file", {"path": "notes.txt"}, "call_2")),
        response(reply("notes.txt 说明：工具执行结果必须通过 call_id 回传。")),
    ], args)


def main():
    args = lesson_args(__doc__)
    if args.demo:
        with TemporaryDirectory(prefix="openai-s02-") as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("工具执行结果必须通过 call_id 回传。", encoding="utf-8")
            run(args, root)
    else:
        run(args, args.workspace)


if __name__ == "__main__":
    main()
