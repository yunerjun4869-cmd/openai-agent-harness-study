"""第三课：写入权限由执行器决定，不由模型自行宣布。"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.fakes import call, reply, response
from harness.filesystem import Workspace


def run(args, root):
    workspace = Workspace(root)
    permitted = bool(args.allow_write)
    ending = "授权写入成功。" if permitted else "写入被执行器拒绝；需要显式 --allow-write。"
    run_example(workspace.tools(), args.prompt or
                "请将 learning.txt 写入内容：权限在工具执行前检查。", [
        response(call("write_file", {"path": "learning.txt", "content": "权限在工具执行前检查。"})),
        response(reply(ending)),
    ], args)
    print(f"实际文件存在：{(Path(root) / 'learning.txt').exists()}")


def main():
    args = lesson_args(__doc__)
    if args.demo:
        with TemporaryDirectory(prefix="openai-s03-") as directory:
            run(args, Path(directory))
    else:
        run(args, args.workspace)


if __name__ == "__main__":
    main()
