# s10：持久化任务系统

上一阶段的待办清单帮助模型安排工作。本章进一步解决程序崩溃、多个执行者抢同一任务、前置任务尚未完成等问题：把任务状态放进 SQLite，并用事务维护认领规则。

## 为什么仅保存一个 JSON 清单还不够

假设任务 B 依赖任务 A，两个 Agent 同时读到 A 为 `pending`。如果“读取”和“改成 running”是分开的，两者可能都执行 A。仅在文件中记录状态不能阻止这种竞态；认领必须是一个原子操作。

| 机制 | 本章实现 | 能回答的问题 |
|---|---|---|
| 持久化 | SQLite 中保存任务、依赖、结果和错误 | 重启后工作进度是否仍在？ |
| 依赖门槛 | 所有前置任务完成后才可认领 | B 为什么还没有开始？ |
| 原子认领 | `BEGIN IMMEDIATE` 事务内选择并更新 | 两个执行者会不会同时抢到任务？ |
| 有期限的认领 | `owner`、`lease_token`、`lease_until` | 执行者消失后能否重新认领？ |
| 防旧执行者提交 | 完成操作校验持有者、令牌与有效期 | 已过期执行者还能覆盖结果吗？ |
| 失败传播 | 前置任务失败使后续任务 `blocked` | 为什么队列里没有可执行任务？ |

`task_claim` 把租约保存在宿主闭包中；模型完成任务时只提供任务 ID 和结果摘要。模型无法靠自填某个 owner 名称冒充另一个执行者。任务结果仍只是流程记录，不能代替 s17 的业务验收证据。

## OpenAI 工具协议如何接入

模型看到的是 `type="function"` 的严格工具 schema。`task_create`、`task_claim` 和 `task_complete` 返回 `function_call` 后，由宿主执行真实数据库操作，并用对应 `call_id` 发回 `function_call_output`。SQLite 状态不放进系统提示词，查询时才作为工具数据提供。

本章所有写状态操作设置 `mutating=True`，仍经过宿主授权。模型输出的依赖名称需要数据库再次验证；严格 JSON 格式无法证明依赖存在或无环。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 `task_tools()`：看模型参数与宿主租约如何分离。
2. [storage.py](../harness/storage.py) 的 `create()`、`add_dependencies()`：看无环依赖与不存在依赖的处理。
3. `claim()`、`complete()`：看事务、租约回收和旧令牌拒绝。
4. [core.py](../harness/core.py)：看工具结果如何回到下一轮 Responses 请求。

## 运行

在 `openai` 目录执行：

```bash
python s10_task_system/code.py --demo
python s10_task_system/code.py --workspace .workspaces --allow-write
```

离线演示使用临时数据库，脚本模拟模型请求，但 SQLite、依赖规则和事务都真实执行。真实模式从 `.env` 或环境变量读取 OpenAI 配置；不提供 `--allow-write` 时会逐次请求终端授权。

预期依次看到 `read` 被认领并完成，随后 `test` 才可认领；末尾列表中两项均为 `completed`。真实模式数据库位于工作目录的 `s10/tasks.sqlite3`，再次运行时先查询已有任务，避免重复创建同名 ID。演示结束后临时数据库清理。

## 练习与判断标准

| 练习 | 验收方式 |
|---|---|
| 让两个线程同时认领一项任务 | 只有一个线程得到有效任务 |
| 用旧 lease token 完成已重新认领的任务 | `complete()` 拒绝写入 |
| 把 A 标为失败，再尝试认领 B | B 为 `blocked`，没有错误执行 |
| 尝试形成 A → B → A | 添加依赖时拒绝，不等到执行阶段卡住 |

本实现没有租约自动续期。任务运行时间需要短于租约；长任务应实现心跳续租，或拆成更小步骤。SQLite 适合本地学习和适度并发；跨多台机器的队列还需要数据库部署、重试、观测和运维设计。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)，本章实现按 OpenAI 协议重新编写。
