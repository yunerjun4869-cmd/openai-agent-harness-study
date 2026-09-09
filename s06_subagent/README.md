# s06 · 子 Agent：委派具体工作，限制上下文与能力

本章回答：父 Agent 如何让另一个 Agent 阅读资料，而不把全部历史与全部工具交给它？

## 本章机制

父 Agent 只有 `delegate_reader` 工具；调用它时，本地 handler 创建一个新 `ResponsesAgent`。子 Agent 使用同一个模型客户端，但拥有新的消息历史、较小预算和只读文件工具。

| 资源 | 父 Agent | 子 Agent |
|---|---|---|
| 工具 | `delegate_reader` | `list_files`、`read_file` |
| 历史 | 用户任务与委派结果 | 仅传入的具体子任务及自己的执行过程 |
| 单次运行预算 | 4 轮、2 次工具调用 | 3 轮、3 次工具调用 |
| 输出 | 汇总结果 | 状态、简短结论、用量 |

这是同步委派：父工具会等子任务返回。并发队列、消息协调和任务认领在 s13 展开。

## 源码导读与 OpenAI 差异

先读 `code.py` 的 `delegate_reader` 闭包：筛选 `not tool.mutating` 的工具，创建新 registry，调用 `child.run(task)`，将返回值转成普通工具结果。再阅读 `harness/core.py`，确认每次 `run` 如何创建与续接历史。

OpenAI Responses API 看到的是两个独立的响应循环。父模型调用一个名为 `delegate_reader` 的函数；子模型不知道自己被其他模型调用，除非你在 instructions 中解释。它不是 API 自动提供的多 Agent 黑盒。

`call_id` 在各自的响应历史中关联结果。不要把子 Agent 的输出项直接拼进父历史；本章只把子任务结果作为父工具的 JSON 输出，避免跨循环混淆调用链。

## 运行与预期

```bash
python s06_subagent/code.py --demo
python s06_subagent/code.py --workspace ./study_data --prompt "委派助手读取 brief.txt 并列出关键结论"
```

真实模式先准备 `study_data/brief.txt` 并配置 `OPENAI_API_KEY`，默认模型 `gpt-6-astra`，可用 `OPENAI_MODEL` 修改。

离线演示在临时目录创建资料，按顺序模拟“父委派 → 子读文件 → 子总结 → 父总结”。本地读取是真实执行；所有模型输出都是脚本编排。演示能验证嵌套循环的接线，不验证真实模型的研究质量。

## 改进、练习与边界

独立历史减少无关信息流入，裁减工具集限制能力，显式返回状态避免把子任务失败包装成无条件成功。子 Agent 不能再次调用委派工具，因此没有无限递归的工具路径。

1. 让子 Agent 请求 `write_file`，观察未知工具拒绝。
2. 缩小子任务轮数，检查父 Agent 是否解释 `budget_exceeded`。
3. 要求子结论附文件路径和短引用，并在父侧核验来源。

本章子预算分别计算，父运行用量不自动合并全部子调用。生产系统应增加共享成本预算、取消传播、超时与调用链追踪。只读工具集也不能消除文件内容中的提示注入，资料始终应作为数据处理。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。委派机制为 OpenAI 响应循环重新实现。
