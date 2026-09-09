# 开发接口约定

本文件供课程维护者使用；学习者从 README.md 开始。

## 主代理负责

`harness/core.py`：
- `Tool(name, description, parameters, handler, mutating=False)`。
- `object_schema(properties)` 返回 strict 兼容对象 schema（全部 required）。
- `ToolRegistry(tools=(), allow_writes=False, approve=None, hooks=())`。
- `registry.execute(name, arguments)`，arguments 是 JSON 字符串，结果是字典。
- `registry.schemas()` 返回 Responses API tools 数组。
- `ResponsesAgent(client, model, registry, max_turns=8, max_tool_calls=24,
  max_context_chars=100000, max_output_tokens=2000, instructions='...')`。
- `agent.run(prompt, history=None)` 返回 `RunResult(status,text,history,usage)`。
- 状态：completed / incomplete / failed / budget_exceeded / context_limit。

`harness/fakes.py`：
- `call(name, arguments, call_id='call_1')` 返回 function_call 项。
- `reply(text)` 返回 assistant message 项。
- `response(*items, status='completed', usage=None)` 返回响应字典。
- `ScriptedClient(responses)` 提供 `.responses.create(**kwargs)` 和 `.requests`。

`harness/cli.py`：
- `lesson_args(description)` 解析 --demo、--prompt、--workspace、--allow-write。
- `make_client(demo_responses, demo)` 返回 client。
- `run_example(tools, prompt, demo_responses, args, instructions='...')`
  构建 registry、运行模型循环、打印结果并返回 RunResult。
- `args.workspace` 为 Path，默认 openai/.workspaces；演示应使用临时目录。
- 环境：OPENAI_API_KEY、OPENAI_MODEL（默认 gpt-6-astra）、OPENAI_BASE_URL（可选）。

`harness/filesystem.py`：
- `Workspace(root)`：`.read_file(path)`、`.write_file(path, content)`、
  `.list_files()`、`.run_command(argv)`、`.tools(include_command=False)`。
- 工具名 read_file、write_file、list_files、run_command；最后一个参数为 argv 数组。
- 所有写入与命令 Tool.mutating=True，由 registry 授权。
- `.run_command` 返回 exit_code、stdout、stderr、timed_out，默认超时 10 秒。

## 状态机制代理负责

请在开发开始时通知其他代理最终接口。
- harness/storage.py：SQLite TaskStore，创建/依赖/原子认领/完成/查询。
- harness/jobs.py：后台任务与持久化定时任务（有界并发、失败状态）。
- harness/workflow.py：带输入摘要和版本的步骤 journal，失败可续跑。
- harness/goal.py：工具证据驱动的有界目标循环，不采信模型自报成功。
- tests/test_state.py 等独立测试。

## 章节分工

- 章节 A：s01_agent_loop、s02_tool_use、s03_permission、s04_hooks、
  s05_todo_write、s06_subagent、s07_skill_loading、s08_context_compact、s09_memory。
  可自行增加 harness/knowledge.py、harness/context.py 及相关测试。
- 章节 B：s10_task_system、s11_background_tasks、s12_scheduler、s13_agent_teams、
  s14_mcp、s15_integrated_harness、s16_workflow_runtime、s17_goal_loop。
  可自行增加 harness/mcp.py、harness/teams.py 和相关测试。
- 每章代码从任意 cwd 可运行：将 Path(__file__).resolve().parents[1] 插入 sys.path。
- 所有章节提供 main()，默认真实模式，--demo 使用明示模拟响应。
- 不需要每章复制完整核心；必须在文档说明哪些共用代码值得追读。
- 每章文档包括问题、机制、OpenAI 对应字段、运行命令、预期现象、练习、边界和链接。
- 原项目仅作课程结构参考，新写实现；列出来源，不复制官方产品宣传结论。
