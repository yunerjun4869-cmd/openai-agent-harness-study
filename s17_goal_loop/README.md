# s17：由工具证据判断完成

模型返回“任务已完成”只代表它给出了最终文本。本章在模型循环外增加目标循环：每轮结束后，宿主运行预先写好的验收器，只有检查通过才把业务目标标记为 completed。

## 一个可以确定验收的目标

生成 `result.json`，严格满足三条规则：

| 规则 | 验收代码检查 |
|---|---|
| 输入数字保持正确 | numbers 精确等于 `[2, 3, 5]` |
| 求和结果正确 | sum 类型是整数且值为 `10` |
| 文件结构正确 | 仅有 numbers 与 sum 两个字段 |

验收器位于宿主 Python 代码中；模型文件工具只开放工作目录，不能编辑验收器。模型可以主动调用 `run_checks` 查看结果，宿主结束时仍独立调用同一检查函数。`Evidence.passed` 来自固定检查器，不能由模型作为工具参数自行填写。

## 两层“完成”需要分开理解

| 状态 | 意义 | 谁判断 |
|---|---|---|
| Responses completed | 本次模型响应已生成完 | OpenAI 服务 |
| Agent completed | 本轮得到最终文本，工具循环停止 | ResponsesAgent |
| Goal completed | 固定验收规则全部通过 | 宿主 GoalLoop + verify |
| budget_exceeded | 有限轮数内仍未达到目标 | 宿主预算规则 |

外层循环最多 3 次 attempt，每次内层 ResponsesAgent 仍有自己的模型轮次、工具次数和上下文预算。失败证据会写入下一轮请求，帮助模型针对真实错误修复；不能只重复“继续努力直到完成”的提示。

## OpenAI 对应字段

写文件和读取检查结果使用标准 `function_call` / `function_call_output`，按 `call_id` 配对。完整 `response.output` 保留在内层会话中。GoalLoop 的 completed 是应用状态，不能从模型 `response.status` 直接复制得出。

本章 `run_checks()` 是固定的进程内检查工具，返回惯例式 `exit_code`、检查数量和失败列表，没有调用 Shell。扩展到代码修复时，可由宿主运行固定测试命令，结合真实进程退出码、测试数量与失败详情生成 Evidence；验收命令和测试文件也需要保护。

## 运行

```bash
python s17_goal_loop/code.py --demo
python s17_goal_loop/code.py --workspace .workspaces --allow-write
```

离线演示故意让第一轮写 `sum=0`，随后模型脚本说“完成了”。宿主检查返回失败，外层循环继续；第二轮改为 10，验收通过后才结束。预期 GoalResult 是 `completed`、`rounds=2`，evidence 中保留一次失败和一次成功。

模型回复是脚本，文件写入和 JSON 检查真实运行。真实模式由实际 OpenAI 模型生成与修复文件，可能第一轮就通过，也可能耗尽预算；不会承诺一定修复成功。真实产物位于工作目录的 `s17/files/result.json`。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 `run_checks()`：固定预期值、文件解析和错误处理。
2. `attempt()`：上次验收详情如何传给下一轮模型。
3. `verify()`：证据来自函数实际结果，不采信模型文本。
4. [goal.py](../harness/goal.py)：Evidence 校验、轮数上限和停止原因。

| 练习 | 验收 |
|---|---|
| 每轮模型都声称成功但不修文件 | 最终 budget_exceeded |
| 写入非法 JSON 或缺失文件 | 固定检查器失败，保留原因 |
| 把 sum 改为 10.0 或 true | 整数类型检查拒绝 |
| 让工具返回假 passed 字段 | verify 不读取该模型可控字段 |
| 扩展为单元测试验收 | 确认真实运行了规定测试，测试数为 0 不得通过 |

Evidence 只是结构，类型本身不认证来源。如果开发者把 verify 写成“解析模型说的 passed”，整个保证就失效。确定验收适合格式、计算、测试等任务；审美和开放研究还需要人工评价、评分标准或额外证据。本例不自动扩大目标，也不在预算结束后偷偷再开新循环。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
