#!/usr/bin/env python3
"""OpenAI Agent 工程课程入口。示例：python run.py s01 --demo。"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def chapters():
    return {path.name[:3]: path for path in sorted(ROOT.iterdir())
            if path.is_dir() and re.fullmatch(r"s\d{2}_.+", path.name)
            and (path / "code.py").exists()}


def main():
    if sys.version_info < (3, 11):
        print("本课程需要 Python 3.11 或更高版本。", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", nargs="?", help="s01–s17 / 1–17 / all（仅离线）")
    parser.add_argument("--list", action="store_true", help="显示课程目录")
    parser.add_argument("--demo", action="store_true", help="离线演示；不调用 OpenAI")
    parser.add_argument("--prompt", help="自定义任务（真实模式）")
    parser.add_argument("--workspace", help="工具工作目录")
    parser.add_argument("--allow-write", action="store_true", help="允许本章写入/命令工具")
    args = parser.parse_args()
    available = chapters()
    if args.list or not args.chapter:
        for key, path in available.items():
            print(f"{key}  {path.name[4:]}")
        if args.list or not sys.stdin.isatty():
            return 0
        print("\n输入课程编号；首次建议使用 python run.py s01 --demo。输入 q 退出。")
        args.chapter = input("run >> ").strip()
        if args.chapter in ("q", "quit", "exit", ""):
            return 0
    key = f"s{int(args.chapter):02}" if args.chapter.isdigit() else args.chapter.lower()
    if key == "all":
        if not args.demo:
            parser.error("all 只用于 --demo 离线验收；真实 API 请逐章运行")
        selected = list(available)
    elif key in available:
        selected = [key]
    else:
        parser.error("未知章节，请使用 --list 查看")
    flags = []
    if args.demo:
        flags.append("--demo")
    if args.allow_write:
        flags.append("--allow-write")
    for name in ("prompt", "workspace"):
        value = getattr(args, name)
        if value is not None:
            flags.extend([f"--{name}", value])
    failed = []
    for selected_key in selected:
        print(f"\n正在运行 {available[selected_key].name}", flush=True)
        outcome = subprocess.run([sys.executable, str(available[selected_key] / "code.py"), *flags])
        if outcome.returncode:
            failed.append(selected_key)
    if len(selected) > 1:
        print(f"\n离线验收：{len(selected) - len(failed)}/{len(selected)} 章通过；失败：{failed}")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
