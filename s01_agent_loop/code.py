"""第一课：一个函数足以看清 Responses 的执行循环。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response


def add(a: int, b: int) -> dict:
    return {"sum": a + b}


def main():
    args = lesson_args(__doc__)
    calculator = Tool("add", "计算两个整数之和", object_schema({
        "a": {"type": "integer"}, "b": {"type": "integer"}}), add)
    run_example([calculator], args.prompt or "请调用 add 计算 17 加 25，并告诉我结果。", [
        response(call("add", {"a": 17, "b": 25})),
        response(reply("工具返回 sum=42，所以答案是 42。")),
    ], args)


if __name__ == "__main__":
    main()
