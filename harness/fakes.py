"""完全离线的确定性脚本响应。仅演示协议，不模拟真实模型的智能和效果。"""
from copy import deepcopy
import json


def call(name, arguments, call_id="call_1"):
    return {"type": "function_call", "id": "fc_" + call_id,
            "call_id": call_id, "name": name, "status": "completed",
            "arguments": json.dumps(arguments, ensure_ascii=False)}


def reply(text):
    return {"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def response(*items, status="completed", usage=None):
    return {"id": "resp_demo", "object": "response", "status": status,
            "output": list(items), "usage": usage or {"input_tokens": 0, "output_tokens": 0}}


class ScriptedClient:
    def __init__(self, responses):
        self._script = iter(responses)
        self.requests = []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        try:
            return deepcopy(next(self._script))
        except StopIteration as exc:
            raise RuntimeError("离线脚本响应已用完；请核对演示是否新增了模型轮次") from exc
