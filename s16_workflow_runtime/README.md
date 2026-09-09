# s16：可恢复工作流

Agent 循环由模型决定下一步，工作流由宿主预先确定步骤顺序。本章固定为“准备输入 → 模型分析 → 发布文件”，将每一步的真实输出保存进 SQLite，在发布失败后复用已经完成的模型分析。

## 为什么要保存步骤结果

只记录“第二步已完成”不够：第三步还需要第二步生成的文本。如果重启后没有结果，就只能重新调用模型，增加费用且可能得到不同内容。因此 journal 同时保存步骤状态和 JSON 可序列化的结果。

| 步骤 | 输入 | 实际结果 | 恢复规则 |
|---|---|---|---|
| prepare | 固定主题 | 主题和字符数 | 成功后直接从 journal 读取 |
| analyze | prepare 的真实输出 | Responses 文本和 usage | 已成功时不再次调用模型 |
| publish | analyze 的真实输出 | 报告路径和字符数 | 失败后重新执行固定覆盖写 |

步骤函数收到 `{"inputs":...,"results":前序已完成结果}`。后面的步骤只读取此前确实产生并保存的结果，不使用凭空构造的占位总结。

## 恢复时如何避免复用错误结果

| 标识 | 校验用途 |
|---|---|
| workflow_id | 指定同一次业务流程 |
| version | 调用方标记流程逻辑版本 |
| 输入摘要 | 输入改变时拒绝继续旧流程 |
| 步骤名称序列 | 增删或调整步骤时拒绝错位恢复 |
| owner 与租约 | 防止有效租约期间两个执行者同时推进 |

同名步骤的 Python 实现变化无法从函数名自动检测，维护者必须提高 version，并使用新的 workflow_id。不能只改代码而继续套用旧步骤结果。当前示例 ID 固定为 `learning-report`、版本为 `1`；改 `--prompt` 后若继续使用旧工作目录，会明确拒绝输入不匹配，可换一个新的 `--workspace` 创建新流程。

## OpenAI 对应字段

模型分析步骤仍使用普通 Responses 工具循环：调用 `read_topic`，以 `call_id` 配对主题数据，然后生成文本。工作流保存实际 `RunResult.text` 和 `usage`。这不是让 OpenAI 负责执行整个持久化工作流；journal、步骤顺序和恢复规则由本地宿主实现。

## 运行

```bash
python s16_workflow_runtime/code.py --demo
python s16_workflow_runtime/code.py --workspace .workspaces
```

离线演示明确注入一次发布故障，随后重新打开数据库并续跑。预期调用次数为 `prepare=1, analyze=1, publish=2`：模型步骤没有重放，失败发布步骤重试一次。模型响应是模拟内容，journal 与报告文件是真实产物。

真实模式不注入故障，报告位于工作目录的 `s16/report.md`。再次相同参数运行，已成功步骤会直接复用数据库结果，可能不会发起新的 API 请求。首次模型步骤需要正常 OpenAI 配置。

## 推荐源码阅读顺序

1. [code.py](code.py) 的三项步骤函数：看真实数据如何流转。
2. [workflow.py](../harness/workflow.py) 的 `_claim()`：输入摘要、版本和租约。
3. `run()` 中 completed 分支：结果反序列化后进入 context。
4. 错误路径与 `inspect()`：步骤失败如何持久化和恢复。

| 练习 | 验收 |
|---|---|
| 故障后重新构建 WorkflowJournal | 第一和第二步不重跑，发布成功 |
| 保持同 ID 改输入 | 明确拒绝，避免混用历史结果 |
| 给两步相同名称 | 启动前报错 |
| 删除报告后再次运行完成的工作流 | 观察 journal 不会自动恢复已删除产物，再设计产物完整性校验 |

动作执行与结果提交之间仍存在崩溃窗口。步骤必须尽量幂等，外部付款、发消息等不能靠 journal 获得“恰好一次”。本例用固定路径覆盖写降低重试风险。没有自动续租，单步运行应短于租约；没有跨服务补偿、分布式 DAG 调度或产物哈希校验。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
