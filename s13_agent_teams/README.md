# s13：有界的多 Agent 团队

一个模型循环可以分头检查不同材料。本章真正创建两个独立的 ResponsesAgent，在最多两个工作线程中分别运行，再由 Python 汇总结果。评审员分析设计风险，测试员提出验收场景。

## 协作前先把边界明确

| 边界 | 本章做法 | 避免的问题 |
|---|---|---|
| 会话 | 每名成员新建 Agent，从空 history 开始 | 成员 A 的工具输出混进成员 B |
| 工作目录 | 每名成员独立目录与 input.txt | 固定教学输入互相覆盖 |
| 工具权限 | 只开放读取和列文件 | 子 Agent 继承主 Agent 的全部写权限 |
| 并发 | 最多 2 个 worker，上层限制任务总数 | 递归派生失控、成本无限放大 |
| 故障 | 每个 Future 独立捕获异常 | 一名成员失败抹掉其他人的成功结果 |
| 汇总 | 以任务原顺序返回结果字典 | 线程完成次序让展示难以复现 |

`run_team()` 接收固定的任务映射与 worker 函数。worker 内创建客户端、工具注册表和 Agent，这个位置决定了成员能看到什么、能做什么。本章调度者是确定的 Python 程序，没有让另一个模型自行扩增团队。

## OpenAI 对应字段

每名成员各自调用 `client.responses.create()`，有独立的 `input` 历史、工具集合和预算。`response.output` 及 `call_id` 只回到产生它们的会话。最后汇总的是成员结论，不能把不同会话的 function_call_output 随意拼接进同一条工具链。

这是一种手写编排方式。OpenAI Agents SDK 也提供 agent、handoff 和 tracing 等抽象，但安装 `openai` Python SDK 并不会自动获得团队调度；本章没有隐藏使用 Agents SDK。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 `worker()`：每次调用构建独立对象，使用自身 input.txt。
2. [teams.py](../harness/teams.py) 的 `run_team()`：名称校验、目录约束、并发上限、异常归并。
3. [core.py](../harness/core.py)：单个成员内部仍是已学过的完整工具循环。

## 运行

```bash
python s13_agent_teams/code.py --demo
python s13_agent_teams/code.py
```

离线模式用脚本代替模型，两条工具循环、线程、读取工具和目录均真实执行。真实模式会并发发起 OpenAI 请求，默认每个成员最多 4 轮模型调用和 4 次工具调用。团队整体预算应乘以成员数评估。

终端输出包含 reviewer、tester 的结果、各自工作目录和历史条数。两种模式均使用临时目录，运行结束清理；`--workspace` 不用于本章固定资料。脚本只汇总各成员回答，未执行结果投票、自动改代码或 Git 合并。

## 目录隔离与安全沙箱的区别

不同目录减少意外覆盖，文件工具还限制路径越界；它们都不等于操作系统安全沙箱。如果开放任意程序执行，进程仍可能访问机器上的其他资源。真正的环境隔离要用容器、低权限账户或隔离运行服务。

处理同一代码仓库时可进一步采用 Git worktree，让每名成员拥有独立分支与检出目录；合并前必须检查差异并运行测试。本实现没有创建 worktree，因此不会把普通临时目录描述成“已完成 Git 隔离”。

| 练习 | 验收 |
|---|---|
| 用事件阻塞 worker，记录同时活跃数 | 活跃数始终不超过 max_workers |
| 让 tester 抛异常 | reviewer 结果仍在，tester 为 failed |
| 为每个成员记录首个 input | 各自只包含自己的请求和资料 |
| 增加综合评审步骤 | 把成员结论当作不可信数据，并给汇总 Agent 独立预算 |

线程超时不是强制终止。当前依靠模型客户端网络超时和各 Agent 的调用预算限制等待；需要可强制终止的长任务时，应把 worker 移到子进程或任务服务。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
