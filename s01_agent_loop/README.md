# s01 · Agent 循环：模型提出调用，程序执行函数

本章回答：给模型一个函数，为什么它就能反复使用工具解决问题？一个可工作的 Agent 不必从框架开始，核心是一个有退出条件的循环。

## 本章要理解的机制

| 步骤 | 本章发生的事 | 对应实现 |
|---|---|---|
| 声明工具 | 告诉模型 `add` 的名称、用途、参数 | `Tool` 与 `object_schema` |
| 请求模型 | 发送用户问题和工具 schema | `client.responses.create` |
| 检查输出 | 找出 `type=function_call` 的输出项 | `ResponsesAgent.run` |
| 本地执行 | 校验参数后调用 Python `add` | `ToolRegistry.execute` |
| 回传结果 | 用原 `call_id` 回传字符串形式的 JSON | `function_call_output` |
| 再次请求 | 模型读取结果，继续调用或形成最终回答 | 有界循环 |

`code.py` 只定义整数加法，用最少业务逻辑暴露执行链。继续阅读 `harness/tools.py` 的 `Tool.schema`、`ToolRegistry.execute`，以及 `harness/core.py` 的 `ResponsesAgent.run`，它们是后续各章共同使用的主干。

## OpenAI 对应关系

Responses API 的函数定义使用扁平格式：`type: function`、`name`、`description`、`parameters`、`strict` 在同一层。不要直接复制 Chat Completions 的 `function: {...}` 外层结构。

严格对象 schema 设置 `additionalProperties: false`，`properties` 中列出的字段全部放入 `required`。可选值需要允许 `null`，并仍然把字段列入 `required`。

一次响应可能有多个输出项。必须保留完整 `response.output`，包括推理模型返回的 reasoning 项，再追加 `function_call_output`。工具调用的 `call_id` 与输出项自身的 `id` 不是同一个用途。

## 运行与预期

先按根目录 README 安装依赖并配置环境。在 `openai` 目录运行：

```bash
python s01_agent_loop/code.py --demo
OPENAI_MODEL=gpt-6-astra python s01_agent_loop/code.py
python s01_agent_loop/code.py --prompt "调用 add 计算 120 加 360"
```

`--demo` 使用明确编排的模拟模型响应，不联网、不计 API 费用。预期第一次模拟响应要求执行 `add(17, 25)`，第二次根据工具返回输出 42。去掉 `--demo` 才会真实调用 OpenAI，需要 `OPENAI_API_KEY`；模型可通过 `OPENAI_MODEL` 修改。

## 相对教学原型的改进

循环有最大轮数、工具次数、上下文字符数与输出 token 限额；未知工具、参数错误、执行失败作为结构化工具结果返回，不靠未捕获异常中断整个会话。回答是否结束还会检查 API 响应状态，避免把截断响应误报为成功。

## 练习与边界

1. 增加 `multiply` 工具，要求模型先乘后加，观察两次 `call_id`。
2. 将工具次数预算设为 1，再请求两步计算，观察 `budget_exceeded`。
3. 在离线测试中让模型请求不存在的工具，检查错误是否回传。

`strict` 提升参数结构可靠性，不能证明工具参数在业务上正确。模型的最终文本也不能替代执行结果；本章的模拟回答只是展示协议。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) · [推理模型](https://developers.openai.com/api/docs/guides/reasoning)

课程结构参考：[原项目 s01](https://github.com/hubooooooo/claude-code-herness-study/tree/main/s01_agent_loop)。本章为 OpenAI Responses API 重新编写。
