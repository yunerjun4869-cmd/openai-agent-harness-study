"""严格 schema、宿主授权、工具分发。模型生成参数后仍须在本地验证。"""
from dataclasses import dataclass
import json
from typing import Callable

from jsonschema import Draft202012Validator, ValidationError


def object_schema(properties: dict) -> dict:
    """可选参数请使用包含 null 的 type；strict 模式仍要求所有字段出现。"""
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    mutating: bool = False

    def schema(self) -> dict:
        return {"type": "function", "name": self.name,
                "description": self.description, "parameters": self.parameters,
                "strict": True}


class ToolRegistry:
    def __init__(self, tools=(), allow_writes=False, approve=None, hooks=()):
        self.tools = {}
        self.allow_writes = allow_writes
        self.approve = approve
        self.hooks = tuple(hooks)
        self.hook_errors = []
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool):
        if tool.name in self.tools:
            raise ValueError(f"工具名称重复：{tool.name}")
        Draft202012Validator.check_schema(tool.parameters)
        self._check_strict(tool.parameters)
        self.tools[tool.name] = tool

    @classmethod
    def _check_strict(cls, node):
        if isinstance(node, dict):
            kind = node.get("type")
            if kind == "object" or isinstance(kind, list) and "object" in kind:
                if node.get("additionalProperties") is not False:
                    raise ValueError("strict 对象必须设置 additionalProperties=false")
                if set(node.get("required", [])) != set(node.get("properties", {})):
                    raise ValueError("strict 对象的全部属性必须 required")
            for value in node.values():
                cls._check_strict(value)
        elif isinstance(node, list):
            for value in node:
                cls._check_strict(value)

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self.tools.values()]

    def _emit(self, event, payload, blocking=False):
        for hook in self.hooks:
            try:
                hook(event, payload)
            except Exception as exc:
                if blocking:
                    raise
                # 工具已经执行时，审计失败不能把成功伪装成未执行。
                self.hook_errors.append({"event": event, "error": type(exc).__name__})

    def execute(self, name: str, arguments: str) -> dict:
        payload = {"name": name}
        try:
            if name not in self.tools:
                raise ValueError(f"未知工具：{name}")
            if len(arguments) > 32768:
                raise ValueError("工具参数超过 32768 字符")
            args = json.loads(arguments)
            tool = self.tools[name]
            Draft202012Validator(tool.parameters).validate(args)
            if tool.mutating and not self.allow_writes:
                if self.approve is None or self.approve(tool, args) is not True:
                    self._emit("denied", payload)
                    return {"ok": False, "error": "PermissionDenied",
                            "message": "宿主未授权此操作"}
            self._emit("before", payload, blocking=True)
            value = tool.handler(**args)
            # 序列化失败也必须成为配对的工具结果，而非打断整个对话。
            json.dumps(value, ensure_ascii=False, allow_nan=False)
            self._emit("after", {**payload, "ok": True})
            return {"ok": True, "result": value}
        except Exception as exc:
            self._emit("error", {**payload, "error": type(exc).__name__})
            # schema 异常 repr 会包含用户原始参数，只返回简要类型与说明。
            message = exc.message if isinstance(exc, ValidationError) else str(exc)
            return {"ok": False, "error": type(exc).__name__, "message": message[:500]}
