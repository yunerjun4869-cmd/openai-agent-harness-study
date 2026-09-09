# 架构与源码阅读顺序

每一章的 code.py 展示本章如何组装运行机制，共用代码负责统一协议与边界。
这样修改工具校验或协议处理时，可以让所有章节同时受益。

## 分层导航

| 层 | 文件 | 职责 |
|---|---|---|
| 课程入口 | [run.py](../run.py) | 发现章节、传递参数、逐章运行与离线验收 |
| 环境配置 | [config.py](../harness/config.py)、[cli.py](../harness/cli.py) | 读取明确的 .env、创建真实/离线客户端、呈现授权与运行状态 |
| 模型循环 | [core.py](../harness/core.py) | 请求模型、记录完整响应、处理工具结果、执行预算与退出状态 |
| 工具契约 | [tools.py](../harness/tools.py) | strict schema、参数校验、授权、hook 与分发 |
| 执行边界 | [filesystem.py](../harness/filesystem.py) | 工作目录检查、原子文件替换、程序超时与输出截断 |
| 上下文与知识 | [context.py](../harness/context.py)、[knowledge.py](../harness/knowledge.py) | 完整轮次裁剪、技能按需读取、带来源的持久化记忆 |
| 持久状态 | [storage.py](../harness/storage.py) | 任务依赖图、事务认领、租约令牌、完成与失败传播 |
| 后台与调度 | [jobs.py](../harness/jobs.py) | 有界并发、结果和异常、持久化到期任务 |
| 团队 | [teams.py](../harness/teams.py) | 独立历史与工作目录下的并行执行 |
| 外部工具 | [mcp.py](../harness/mcp.py) | 真实远程 MCP 白名单、逐次授权和响应链 |
| 工作流 | [workflow.py](../harness/workflow.py) | 版本/输入摘要校验、步骤 journal、恢复与并发保护 |
| 目标 | [goal.py](../harness/goal.py) | 有界尝试、应用预设验收、证据与准确退出状态 |
| 离线协议 | [fakes.py](../harness/fakes.py) | 可重复脚本响应，记录实际请求，便于测试 |

## 跟着一次工具调用读代码

1. 打开 s01/code.py，找到 `Tool` 声明和 `run_example`。
2. 在 cli.py 查看如何选择真实 SDK 客户端或 ScriptedClient。
3. 在 tools.py 查看 `object_schema`、`schemas()` 和 `execute()`。
4. 在 core.py 查看 `responses.create`、`history.extend(items)` 和 `call_id` 配对。
5. 运行 `python run.py s01 --demo`，然后读 `tests/test_protocol.py` 的错误输入案例。
6. 阅读 s03 和 s17，区分“允许执行”“会话结束”“验收通过”三种状态。

## 运行状态不混用

| 状态来源 | 表示什么 | 不表示什么 |
|---|---|---|
| 工具结果 `ok=true` | handler 正常返回了可序列化结果 | 返回的命令 exit_code 一定为 0 |
| Agent `completed` | 收到完成响应和最终文本 | 用户的业务目标已经达成 |
| TaskStore `completed` | 合法 owner 在有效租约内提交完成记录 | 数据库自动验证过文件或测试 |
| GoalResult `completed` | 应用固定验收回调返回通过证据 | 未被验收器覆盖的需求也一定满足 |

## 怎样添加一章或一个工具

工具使用 `Tool` 声明参数和 mutating 标记，加入 registry，不修改核心 while 循环。
含副作用工具还需要说明幂等、权限和错误结果，必要时添加有针对性的测试。
新章节目录使用 `sNN_主题`，提供 README.md、code.py 与明确的 --demo。
开发接口约定见 [IMPLEMENTATION.md](../IMPLEMENTATION.md)，工作指南见 [AGENTS.md](../AGENTS.md)。
