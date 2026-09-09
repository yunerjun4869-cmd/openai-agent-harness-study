# 从 Anthropic 工具调用迁移到 OpenAI

迁移的关键是消息协议与状态管理，不是把包名和模型名替换一下。
本课程使用 Responses API。Chat Completions 仍有不同的消息格式，不能混用。

## 字段对照

| 目的 | Anthropic 示例常见写法 | 本课程 OpenAI Responses 写法 |
|---|---|---|
| 客户端 | `Anthropic()` | `OpenAI()` |
| 模型调用 | `client.messages.create(...)` | `client.responses.create(...)` |
| 系统指令 | `system=...` | `instructions=...`，每次请求重新传入 |
| 输入历史 | `messages=[...]` | `input=[...]` |
| 函数定义 | `name`、`input_schema` | `type="function"`、`name`、`parameters`、`strict=True` |
| 模型请求工具 | `tool_use` block | `response.output` 中的 `function_call` item |
| 工具参数 | `block.input` 对象 | `item.arguments` JSON 字符串，需解析并验证 |
| 配对标识 | `tool_use_id=block.id` | `call_id=item.call_id`，不要用 item.id 替代 |
| 工具结果 | user 消息中的 `tool_result` | 独立 `function_call_output` item，`output` 为字符串 |
| 最终文本 | 读取 text blocks | `response.output_text`；底层也可遍历 message 的 output_text |
| 历史保存 | assistant content blocks | 完整 `response.output`，包括不透明的 reasoning 项 |

Responses 的工具定义是扁平结构，不使用 Chat Completions 的外层 `function: {...}`：

```python
tool = {
    "type": "function",
    "name": "read_file",
    "description": "读取工作目录内的文件",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
}
```

strict 模式要求对象禁止额外属性，所有声明属性都出现在 required 中。
可选值用 `"type": ["string", "null"]` 表示；嵌套对象也必须符合限制。
模型请求通过 API schema 检查后，宿主仍使用 jsonschema 再次验证和独立授权。

## 两种状态方式分别学习

| 方式 | 课程位置 | 保存内容 | 注意事项 |
|---|---|---|---|
| 客户端维护历史 | s01–s13、s15–s17 | 本地完整 input/output；请求 `store=False` | 工具链与 reasoning 项需要一起回传，不应只保存最终文本 |
| API 响应链 | s14 | `previous_response_id`；下一轮仅提交新的审批结果 | 使用 `store=True`，本地另外保留输出供学习审计；遵循账户数据策略 |

不要同时重复提交完整历史又用 previous_response_id 重复引用同一段历史。
`instructions` 在本课程两种循环中都每轮发送；不能假定上一轮指令会自动继承。
根据核对时的官方 reasoning 文档，`store=False` 下 reasoning 输出默认包含加密内容，
不再要求额外指定 `include=["reasoning.encrypted_content"]`。保留返回的 item 即可，不解析加密内容。

## 迁移中最容易漏掉的情况

1. 一次响应可能包含 reasoning、文本和多个工具项；循环必须完整保存、逐一配对。
2. `incomplete` 不是完成，即使出现工具项也可能存在截断参数，本课程拒绝执行。
3. 工具异常、参数错误和权限拒绝需要返回结构化结果，让模型知道发生了什么。
4. 重复 call_id 应拒绝执行；跨会话恢复需要真实执行日志与幂等设计，单次内存缓存不够。
5. 模型没有再次调用工具仅意味着这一轮结束，不能证明用户目标已经达到。
6. 网络重试由 SDK 限制次数；不能把整套“模型请求 + 本地工具副作用”直接放进自动重试。

对照代码：[core.py](../harness/core.py)、[tools.py](../harness/tools.py)、[mcp.py](../harness/mcp.py)。
官方来源见 [SOURCES.md](SOURCES.md)。
