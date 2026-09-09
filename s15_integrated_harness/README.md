# s15：把机制接进同一条运行链

单章演示能解释机制，但真实任务需要各部分共同工作。本章把文件工具、宿主授权、工具审计、持久化任务和预算控制接到同一个 ResponsesAgent，完成“登记任务 → 生成报告 → 回读 → 更新记录”。

## 这次实际集成了什么

| 机制 | 本章接入点 | 可观察证据 |
|---|---|---|
| 文件工具 | Workspace | report.md 实际写入并可回读 |
| 权限 | ToolRegistry + approve_tool | 写文件和任务状态更新经过宿主授权 |
| 审计 hook | `audit(event, payload)` | 终端输出每个工具的 before/after/denied/error |
| 任务状态 | TaskStore + s10 的 task_tools | SQLite 保存认领和完成记录 |
| 资源预算 | ResponsesAgent 构造参数 | 8 轮模型调用、16 次工具调用和上下文上限 |

后台任务、定时器、团队、远程 MCP、工作流和目标循环各有生命周期，本章没有把它们全部注册成“自动可用”。这些机制可根据实际产品需要选择接入；尤其远程 MCP 审批需要 s14 的专用协议处理，不能仅加一个本地函数名就声称支持。

## 一次调用经过哪些阶段

```text
模型 function_call
    ↓ 严格参数校验
宿主权限判断
    ↓ 审计 before
文件 / SQLite 工具
    ↓ 审计 after 或 error
function_call_output(call_id)
    ↓ 保留完整 output 和历史
下一轮 Responses API
```

本章沿用 `store=False` 和客户端完整历史。工具输出只作为数据回到模型，工具权限仍留在 Python 宿主。任务状态文件位于 `state/`，模型文件工具只开放 `files/`，减少模型覆盖自身任务数据库的机会。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 root/files 与 root/state：看模型可写范围与运行状态如何分开。
2. `ToolRegistry(...)`：权限、hook、工具集合在同一个地方组装。
3. [s10 的 task_tools](../s10_task_system/code.py)：复用认领契约，没有另写简化任务表。
4. [tools.py](../harness/tools.py)：工具执行后 hook 出错不会把已执行副作用伪装成未执行。
5. [core.py](../harness/core.py)：错误、重复 call_id 与资源预算的处理。

## 运行

```bash
python s15_integrated_harness/code.py --demo
python s15_integrated_harness/code.py --workspace .workspaces --allow-write
```

离线脚本驱动真实文件和数据库操作，临时目录在结束时清理。真实模式生成的报告位于工作目录下 `s15/files/report.md`，任务数据库位于 `s15/state/tasks.sqlite3`；再次运行可让模型检查已有记录。

预期输出有报告生成说明、工具审计列表、任务状态和文件列表。示例是最小集成：审计保存在当前进程内存，没有声称建立可查询的生产日志平台。`--allow-write` 授权本章提供的修改操作；省略时终端逐次确认，非交互输入拒绝。

## 练习与边界

| 练习 | 验收 |
|---|---|
| 拒绝 write_file | 不产生报告，审计中记录 denied |
| 让 before hook 抛异常 | 工具未执行，返回配对的错误结果 |
| 让 after hook 抛异常 | 已执行结果保持成功，hook 错误另存 |
| 加入 MemoryStore 查询工具 | 记忆仍是带来源的数据，不能覆盖宿主权限 |
| 把业务验收接成 s17 GoalLoop | 模型说完成之后，独立检查真正的交付物 |

`task_complete` 只记录“当前执行者提交了完成结果”。即使模型已回读文件，也不等于报告内容满足所有要求。确定的业务验收应由可信代码定义，下一阶段会展示这种完成判断。这里没有任意 Shell 工具，也没有操作系统沙箱。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
