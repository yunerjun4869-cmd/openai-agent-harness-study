"""第八课：按完整用户轮次裁剪，保留函数调用链。"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, make_client
from harness.context import compact_history
from harness.core import ResponsesAgent, Tool, ToolRegistry, object_schema
from harness.fakes import call, reply, response


def main():
    args = lesson_args(__doc__)
    facts = Tool("course_facts", "重新读取课程的上下文管理原则", object_schema({}), lambda: {
        "principle": "保留完整 response.output；裁剪只能删除旧的完整用户轮次。",
        "limitation": "删除旧轮次会丢失信息，必要时应重新检索。"})
    client = make_client([
        response(call("course_facts", {})),
        response(reply("已读取课程要点。")),
        response(call("course_facts", {}, "call_2")),
        response(reply("重新读取要点：按完整轮次裁剪会丢失旧信息；不能拆开工具调用链。")),
    ], args.demo)
    agent = ResponsesAgent(client, os.getenv("OPENAI_MODEL", "gpt-6-astra"), ToolRegistry([facts]))
    initial = "读取课程的上下文管理要点。"
    if args.demo:
        initial += "以下是用于触发裁剪的模拟冗长背景：" + "历史背景。" * 900
    first = agent.run(initial)
    if first.status != "completed":
        print(f"首轮状态：{first.status}\n{first.text}")
        raise SystemExit(1)
    followup = args.prompt or "再次调用工具读取要点，解释裁剪上下文的代价。"
    # 把下一条用户消息先加入预算计算，防止裁剪后追加 prompt 又超出预算。
    candidate = first.history + [{"role": "user", "content": followup}]
    compacted = compact_history(candidate, max_chars=3000)
    print(f"历史字符：{compacted.original_chars} → {compacted.retained_chars}；"
          f"删除旧消息 {compacted.removed_messages} 条（字符不等于 token）。")
    # run 会添加用户消息，因此移除刚才仅用于预算计算的最后一项。
    result = agent.run(followup, history=compacted.history[:-1])
    print(f"状态：{result.status}\n{result.text}")
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
