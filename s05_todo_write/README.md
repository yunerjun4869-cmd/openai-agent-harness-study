# s05 · 会话计划：让下一步清晰，并约束无效状态

本章回答：长任务为什么容易“说了一堆计划，却没有持续跟踪”？把计划变成可校验的状态，模型每次更新都能得到当前进度。

## 机制与源码导读

`TodoBoard` 在当前 Python 进程内保存任务列表。`update_todos` 接收整份新计划，校验后一次替换，返回列表和完成数量。

| 约束 | 目的 | 实现位置 |
|---|---|---|
| 最多 12 项 | 避免计划长到无人维护 | `TodoBoard.update` |
| id 唯一，描述非空 | 让每项可明确指认 | `TodoBoard.update` |
| 最多一项进行中 | 让下一步可读 | `TodoBoard.update` |
| 状态仅三种 | 拒绝拼错或未知状态 | 工具 JSON schema |

`TodoBoard.tool` 展示嵌套对象与数组的严格 schema。执行器完成结构校验，业务方法负责“只能有一个进行中”这样的跨字段规则。

计划工具只改变会话内的 Python 状态，不写外部文件，因此没有标为 `mutating=True`。跨进程持久任务、依赖和原子认领在 s10 展开。

## OpenAI 差异

Responses API 没有自动附带本课程的 Todo 工具；它是普通 `function` 工具。数组中的对象也必须设置 `additionalProperties: false`，其中的 `id`、`text`、`status` 全部放入 `required`。

模型说“我已完成”是一段文本；调用 `update_todos` 是修改应用状态。**两者都不能证明实际工作已经完成**。把执行证据与完成条件绑定是 s17 的内容。

## 运行与预期

```bash
python s05_todo_write/code.py --demo
python s05_todo_write/code.py --prompt "先用计划工具安排三步学习 Responses 函数调用，再开始第一步"
```

`--demo` 不联网，使用两次模拟工具调用：先把“理解工具循环”设为进行中，再标为完成并开始“解释 call_id”。最终文本会解释关联机制，同时如实保留一项进行中，展示文本回答结束与业务任务完成是不同状态。

真实模式需要 `OPENAI_API_KEY`；默认模型 `gpt-6-astra`，通过 `OPENAI_MODEL` 可修改。每次重新运行程序会创建空白计划。

## 改进、练习与边界

1. 构造两项 `in_progress`，确认更新失败且旧计划保持原样。
2. 添加依赖字段，思考“前置任务尚未完成，能否开始后续任务”。
3. 增加“完成时附带工具证据 id”规则，并在本地验证证据真实存在。

本章使用全量替换，模型可以删项或重置已完成项；这适合会话草稿，不能当作不可篡改的任务账本。外部任务系统还需要状态迁移、版本冲突与审计。本章也不自动持久化，以免把会话计划误当长期记忆。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。业务约束为本课程重新设计。
