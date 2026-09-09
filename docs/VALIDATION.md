# 验证记录

验证日期：2026-09-10（北京时间）。
环境：macOS、Python 3.13.5、openai 2.54.0、jsonschema 4.26.0、pytest 9.1.1。
安装版本快照见 [requirements-lock.txt](../requirements-lock.txt)。

## 已完成的验证

| 检查 | 实际结果 |
|---|---|
| `python -m pytest -q` | **66 passed** |
| `python run.py all --demo` | **17/17 章通过**，全部退出码 0 |
| Python 编译检查 | 全部课程、共享模块和测试通过 |
| s03 离线拒绝写入 | 工具返回 PermissionDenied，实际目标文件不存在 |
| s03 显式允许写入 | 文件实际存在，工具返回成功 |
| s09 记忆写入权限 | 默认拒绝新增；授权后记录数由 1 增为 2，仍为未审阅 |
| s14 SDK 协议 | 真实 SDK 经 HTTP MockTransport 生成 MCP 请求和审批响应链；没有联网 |
| s16 发布故障恢复 | prepare/analyze/publish 实际调用数为 **1/1/2** |
| s17 模型自报完成 | 第 1 轮验收失败，第 2 轮通过；最终 evidence 保留两次结果 |
| 从其他工作目录启动 | 在 `/tmp` 调用绝对路径入口正常定位课程 |
| 未配置 API Key | 明确提示缺少 OPENAI_API_KEY，退出码 1；没有自动转为模拟模式 |
| GitHub Actions：Ubuntu + Python 3.11 | 安装依赖、66 项测试、17 章离线演示全部通过 |
| GitHub Actions：Ubuntu + Python 3.13 | 安装依赖、66 项测试、17 章离线演示全部通过 |

首次公开发布的 CI 记录：[运行 34385122748](https://github.com/yunerjun4869-cmd/openai-agent-harness-study/actions/runs/34385122748)。
Windows 目前提供命令指南，尚未完成同等实机测试；创建符号链接的测试受系统权限影响。

## 测试分别验证什么

| 测试文件 | 覆盖行为 |
|---|---|
| [test_protocol.py](../tests/test_protocol.py) | reasoning 完整回传、多工具配对、参数错误、未知工具、handler 异常、incomplete、重复 call_id、预算、权限、hook、跨历史恢复 |
| [test_sdk_transport.py](../tests/test_sdk_transport.py) | 安装的 OpenAI SDK 实际请求序列化、Responses 路径、扁平 schema 和输出解析 |
| [test_filesystem.py](../tests/test_filesystem.py) | 路径穿越、绝对路径、外部符号链接、凭证目录、文件回读、命令参数、密钥环境过滤、真实进程超时与输出上限 |
| [test_knowledge_context.py](../tests/test_knowledge_context.py) | 技能目录、文件边界、完整轮次裁剪、超限拒绝、来源记忆、Todo 状态 |
| [test_state_storage.py](../tests/test_state_storage.py) | 依赖循环、事务回滚、失败传播、有效租约、旧令牌拒绝、线程与 spawn 多进程竞争 |
| [test_state_jobs.py](../tests/test_state_jobs.py) | 后台容量、异常、超时、结果序列化、到期动作白名单与调度恢复 |
| [test_state_workflow.py](../tests/test_state_workflow.py) | 输入/版本/步骤隔离、失败续跑、真实子进程崩溃后的重放边界 |
| [test_state_goal.py](../tests/test_state_goal.py) | 模型文字不参与验收、失败证据、有界尝试、验收异常 |
| [test_mcp_teams.py](../tests/test_mcp_teams.py) | MCP 批准/拒绝/白名单/失败/截断、SDK 审批链、目录隔离与并发上限 |
| [test_goal_cli.py](../tests/test_goal_cli.py) | 内层 Agent CLI 失败转换为可检查的 GoalResult.failed |

## 复现方式

在 openai 目录且虚拟环境已安装依赖的情况下：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python run.py all --demo
.venv/bin/python run.py s03 --demo --allow-write
.venv/bin/python run.py s17 --demo
```

也可以在新的虚拟环境安装 `requirements-lock.txt` 后运行。
安装范围由 requirements.txt / requirements-dev.txt 声明，版本快照仅记录本次验收环境。

## 未执行的验证

本次没有使用真实 OpenAI API Key 发起模型请求，也没有连接实际远程 MCP 服务。
模型生成质量、账户权限、网络可达性和远程服务认证仍需在实际部署环境验证。
离线脚本不是模型评测，66 项测试也不代表所有输入或并发条件都已覆盖。
