#!/usr/bin/env python3
"""运行离线课程，将真实输出排成可截图的本地 HTML；不调用真实 OpenAI。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "previews"
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if (ROOT / ".venv/Scripts").exists() else "bin/python")

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; background: #f2f5f9; color: #17243a;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }
main { width: 1100px; max-width: 100%; padding: 35px 42px 30px; margin: auto; }
.eyebrow { color: #355779; font-size: 14px; font-weight: 650; letter-spacing: 1px; }
h1 { margin: 11px 0 10px; font-size: 31px; line-height: 1.35; font-weight: 750; }
.intro { font-size: 16px; line-height: 1.7; margin: 0 0 17px; color: #46576d; }
.badges { display: flex; gap: 9px; margin-bottom: 19px; }
.badge { border-radius: 6px; background: #e1edff; color: #245487; padding: 6px 10px; font-size: 13px; }
.badge.green { background: #deefe7; color: #22674b; }
.terminal { border-radius: 12px; overflow: hidden; background: #142033; box-shadow: 0 7px 22px #26375216; }
.terminal-header { padding: 12px 20px; background: #1e2c43; font-size: 13px; color: #c0cee2; }
.command { padding: 17px 20px 14px; color: #82c9ff; font-size: 15px; border-bottom: 1px solid #ffffff17; }
pre { margin: 0; padding: 18px 20px 20px; color: #e0e9f5; white-space: pre-wrap;
  overflow-wrap: anywhere; line-height: 1.65; font-size: 14px; }
code, pre { font-family: "SFMono-Regular", Menlo, Consolas, "Microsoft YaHei", monospace; }
.note { background: #fff; border: 1px solid #dfe6ef; border-left: 4px solid #509478;
  border-radius: 7px; margin-top: 17px; padding: 13px 16px; font-size: 14px; line-height: 1.75; }
.note strong { color: #21644b; }
footer { color: #6c7b8f; font-size: 12px; line-height: 1.65; margin-top: 16px; }
.all pre { font-size: 13px; line-height: 1.5; }
"""


def run(chapter):
    result = subprocess.run([str(PYTHON), "run.py", chapter, "--demo"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode:
        raise RuntimeError(f"{chapter} 离线运行失败，退出码 {result.returncode}；拒绝生成成功页面。")
    return result.stdout.strip()


def check_public_text(text):
    """记录页仅使用精选输出；禁止将宿主路径或可能的密钥带入公开截图。"""
    patterns = [r"/Users/", r"/home/", r"/private/", r"/var/folders/", r"[A-Za-z]:\\Users\\",
                r"sk-[A-Za-z0-9_-]{16,}", r"gh[pousr]_[A-Za-z0-9]{16,}"]
    if any(re.search(pattern, text) for pattern in patterns):
        raise ValueError("页面内容出现本机路径或疑似密钥，停止生成。")


def page(title, intro, chapter, content, note, timestamp, compact=False):
    check_public_text(content)
    command = f"python run.py {chapter} --demo"
    return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · OpenAI Agent Harness Study</title>
<style>{STYLE}</style>
<main class="{'all' if compact else 'lesson'}">
  <div class="eyebrow">OPENAI AGENT HARNESS STUDY · 运行记录</div>
  <h1>{escape(title)}</h1>
  <p class="intro">{escape(intro)}</p>
  <div class="badges">
    <span class="badge">实际运行记录的排版展示</span>
    <span class="badge green">模型响应为离线脚本 · 无 API 费用</span>
  </div>
  <section class="terminal" aria-label="真实离线运行输出">
    <div class="terminal-header">本地运行结果 · Python 虚拟环境</div>
    <div class="command"><code>$ {escape(command)}</code></div>
    <pre>{escape(content)}</pre>
  </section>
  <div class="note">{note}</div>
  <footer>记录生成时间：{escape(timestamp)}<br>
  这是 HTML 排版页的浏览器截图来源，不是原生终端截图。命令中的 python 指项目虚拟环境里的 Python。</footer>
</main>
</html>
"""


def main():
    if not PYTHON.is_file():
        raise SystemExit("请先按 README 创建 .venv 并安装 requirements-dev.txt。")
    with ThreadPoolExecutor(max_workers=3) as pool:
        first, all_output, goal = list(pool.map(run, ["s01", "all", "s17"]))
    if "[工具] add → 成功" not in first or "[状态] completed" not in first or "sum=42" not in first:
        raise RuntimeError("第一课输出不符合预期，拒绝生成成功页面。")
    chapter_lines = [line for line in all_output.splitlines() if line.startswith("正在运行 s")]
    expected = [f"正在运行 {path.name}" for path in sorted(ROOT.glob("s[0-9][0-9]_*"))
                if (path / "code.py").is_file()]
    summaries = [line for line in all_output.splitlines() if line.startswith("离线验收：")]
    if len(chapter_lines) != 17 or chapter_lines != expected or summaries != ["离线验收：17/17 章通过；失败：[]"]:
        raise RuntimeError("全课程运行记录未确认 17/17 通过，拒绝生成成功页面。")
    checks = [line for line in goal.splitlines() if line.startswith("独立工具验收：")]
    reports = [json.loads(line.split("：", 1)[1]) for line in checks]
    final = json.loads(goal.split("目标结果：", 1)[1])
    if ([report["exit_code"] for report in reports] != [1, 0]
            or final["status"] != "completed" or final["rounds"] != 2):
        raise RuntimeError("目标验收记录没有确认先失败再成功，拒绝生成成功页面。")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    all_excerpt = "\n".join(chapter_lines + ["", *summaries])
    goal_excerpt = "\n\n".join(checks) + "\n\n目标结果（节选）：\n" + json.dumps(
        {"status": final["status"], "rounds": final["rounds"]}, ensure_ascii=False, indent=2)
    pages = {
        "first-lesson.html": page("第一课跑通了：17 + 25 = 42", "观察一次完整过程：请求工具 → Python 计算 → 回传结果 → 输出答案。",
            "s01", first, "<strong>看见这三点就成功：</strong>add 工具执行成功、状态 completed、答案为 42。"
            "本页保留第一课完整输出；requests: 2 表示两轮模拟响应。", timestamp),
        "all-lessons.html": page("17 章离线演示，全部运行通过", "每行章名都来自实际执行记录；末行汇总确认本次所有课程均正常退出。",
            "all", all_excerpt, "<strong>已折叠中间工具输出：</strong>本页仅列出 17 个实际运行章名与最终汇总。"
            "你运行同一命令时会看到完整过程；其中 s03 的写入拒绝属于预期演示。", timestamp, compact=True),
        "goal-check.html": page("模型说完成后，还要检查结果", "第 17 课故意先写错答案，宿主检查失败；第二轮修复后，独立验收才通过。",
            "s17", goal_excerpt, "<strong>第一次 exit_code=1：</strong>sum 不等于 10，验收失败。"
            "<br><strong>第二次 exit_code=0：</strong>三项检查通过，最终 completed，合计 2 轮。"
            "本页仅展示两条真实验收记录与最终状态，已折叠其他工具输出。", timestamp),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, html in pages.items():
        if len(html.splitlines()) > 200:
            raise ValueError("页面超过单次 200 行写入限制。")
        (OUTPUT / name).write_text(html, encoding="utf-8")
        print(f"已生成 assets/previews/{name}")


if __name__ == "__main__":
    main()
