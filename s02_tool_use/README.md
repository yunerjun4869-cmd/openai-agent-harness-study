# s02 · 工具系统：从函数计算到操作工作目录

本章回答：当 Agent 可以列文件、读文件、写文件时，如何让工具接口清晰，并限制它实际接触的范围？

## 本章机制与源码导读

| 阅读位置 | 学习重点 |
|---|---|
| `code.py` 的 `run` | 将 `Workspace.tools()` 注册到同一个模型循环 |
| `harness/filesystem.py` 的 `Workspace` | 把模型提供的相对路径解析到固定工作目录 |
| `harness/tools.py` 的 `ToolRegistry` | 工具名分发、JSON 参数解析、schema 校验、错误封装 |
| `harness/fakes.py` | 用三次模拟响应固定重现“列目录 → 读文件 → 总结” |

工具描述是模型选择工具的重要线索，参数 schema 是输入契约，handler 是真实执行代码。三者各有职责。即使模型生成了合法 JSON，也需要检查路径和权限。

## OpenAI 差异

工具是由你提供的 Python 程序执行的。Responses API 返回的 `function_call` 本身不读取你的本地文件；只有执行器调用 handler 才产生访问。返回内容必须序列化为字符串放入 `function_call_output.output`，并匹配原始 `call_id`。

工具列表使用 `tools=[...]` 传入。模型可以一次请求多个工具；执行器保留原始输出顺序并将每项结果关联到对应调用。本课程默认串行执行本地工具，便于解释文件依赖。

## 运行与预期

在 `openai` 目录运行：

```bash
python s02_tool_use/code.py --demo
python s02_tool_use/code.py --workspace ./study_data --prompt "列出文件并概括 notes.txt"
```

第二条命令需要先在 `study_data` 中放置文本文件，并设置 `OPENAI_API_KEY`。默认模型是 `gpt-6-astra`，可用 `OPENAI_MODEL` 覆盖。

`--demo` 在临时目录写入教学夹具 `notes.txt`，随后真实执行列表与读取工具，LLM 响应由脚本模拟。正常预期是读到“工具执行结果必须通过 call_id 回传”。临时目录随演示结束自动清理；没有把假模型当作真实 API 验证。

## 改进与限制

| 原型常见问题 | 本课程处理 |
|---|---|
| 模型传入 `../../` 读取任意位置 | 规范化路径并验证仍在工作目录中 |
| 通过符号链接跳出目录 | 检查解析后的真实路径 |
| 工具名称或字段拼错导致进程崩溃 | 返回结构化错误供模型调整 |
| 读一个巨大文件耗尽上下文 | 读取限制与循环预算共同约束 |

路径约束是应用层边界，不能代替操作系统沙箱。存在其他进程并发修改路径、硬链接或任意命令执行时，还需要额外隔离。命令执行将在综合章节中讨论，本章无需开启它。

## 练习

1. 在临时目录中测试绝对外部路径、`../`、指向目录外的符号链接。
2. 为读取工具设计分页参数，并考虑严格 schema 的 `required` 要求。
3. 请求不存在的文件，查看模型是否依据真实错误重试或说明限制。

官方阅读：[函数调用与工具结果](https://developers.openai.com/api/docs/guides/function-calling) · [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)

课程结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。代码按 OpenAI 协议重新实现。
