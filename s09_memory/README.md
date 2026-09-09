# s09 · 长期记忆：保存来源，而不是永久相信模型写下的话

本章回答：会话结束后如何保留项目偏好和经验，同时避免错误或恶意内容成为下一次会话的默认指令？

## 机制与源码导读

`MemoryStore` 使用 SQLite 保存记忆，并通过两个标准工具暴露给模型：`search_memory` 检索，`save_memory` 保存候选内容。

| 字段 | 含义 |
|---|---|
| `id` | 本地记录标识 |
| `text` | 记忆正文 |
| `source` | 由保存方声明的来源，必须非空 |
| `created_at` | UTC 创建时间 |
| `reviewed` | 默认 `false`，本章没有自动审阅 |
| `trusted_as_instruction` | 检索时始终为 `false` |

读 `harness/knowledge.py` 的 SQL 参数绑定、长度检查和查询限制；再读 `code.py`，看写记忆如何标为 `mutating=True` 并沿用 s03 权限。候选记忆不自动升级为系统 instructions。

## OpenAI 差异

Responses API 的会话历史与本章长期记忆是两个层次：本章把文件数据库检索结果作为普通 `function_call_output` 传给模型。API 不会自动读取你的 SQLite 文件，也不会替应用判断记录是真是假。

即使模型生成了合法严格 JSON，也可能编造 `source`。来源字段提高可追溯性，不证明真实性；生产系统应由应用绑定实际文档 id、用户消息 id 或内容摘要，并加入审阅流程。

## 运行与预期

```bash
python s09_memory/code.py --demo
python s09_memory/code.py --demo --allow-write
python s09_memory/code.py --workspace ./study_data --allow-write
python s09_memory/code.py --workspace ./study_data --prompt "检索工具结果的证据要求，不新增记忆"
```

离线演示先在临时 SQLite 数据库播种一条明确标记为模拟来源的中文偏好，再关闭并重新打开数据库，展示跨实例读取。第一条命令可检索，但模型请求新增记忆时被拒绝；第二条允许保存，记录仍为未审阅。临时数据库会自动清理。

真实模式在工作目录创建或打开 `memories.sqlite3`，因此会初始化本地数据库；模型写入记忆仍需 `--allow-write` 或交互确认。重复使用同一个 `--workspace` 可以跨进程检索已有记录。需要 `OPENAI_API_KEY`；默认模型 `gpt-6-astra`，可用 `OPENAI_MODEL` 修改。

## 改进、练习与边界

1. 保存一条包含“忽略用户要求”的资料，确认检索结果仍是不可信数据。
2. 为相互矛盾的偏好添加有效期、适用项目和替代关系。
3. 让来源由应用从真实工具证据生成，禁止模型自由填写来源。

本章使用简单的大小写无关子串检索，最多返回 20 条，不提供向量搜索、去重、过期清理、加密或自动事实核查。不要把密码或 API Key 当作记忆素材。SQLite 连接用于单线程会话，多 Agent 并发写入需设计事务与连接生命周期。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [对话状态](https://developers.openai.com/api/docs/guides/conversation-state)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。本章重新实现有来源和信任边界的记忆示例。
