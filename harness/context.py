"""以完整用户轮次为单位裁剪历史；不拆开函数调用与函数返回。"""
from dataclasses import dataclass
import json


class ContextOverflow(ValueError):
    """当前轮次本身超过预算，不能安全裁剪。"""


@dataclass(frozen=True)
class CompactResult:
    history: list[dict]
    removed_messages: int
    original_chars: int
    retained_chars: int


def history_chars(history: list[dict]) -> int:
    """这是本地字符预算，不是模型 tokenizer 的 token 估计。"""
    return len(json.dumps(history, ensure_ascii=False, separators=(",", ":")))


def compact_history(history: list[dict], max_chars: int) -> CompactResult:
    """保留最新完整用户轮次和开头的固定上下文，依次丢弃更早轮次。"""
    if max_chars <= 0:
        raise ValueError("字符预算必须大于零")
    original = history_chars(history)
    if original <= max_chars:
        return CompactResult(list(history), 0, original, original)
    starts = [i for i, item in enumerate(history) if item.get("role") == "user"]
    if not starts:
        raise ContextOverflow("没有用户轮次边界，不能安全裁剪；请开始新会话")
    prefix = history[:starts[0]]
    for start in starts[1:]:
        retained = prefix + history[start:]
        size = history_chars(retained)
        if size <= max_chars:
            return CompactResult(retained, start - len(prefix), original, size)
    raise ContextOverflow("最新用户轮次仍超过预算；拒绝截断工具调用链，请开始新会话")
