# s14：OpenAI 远程 MCP 与逐次审批

MCP 让外部服务以统一协议公开工具。本章使用 Responses API 原生 `type="mcp"`，学习工具发现、调用审批和返回结果。真实模式的连接由 **OpenAI 服务端** 发起，目标是你提供的 HTTPS MCP 服务。

## 先区分两条连接路径

| 路径 | 谁连接 MCP | 本章是否实现 |
|---|---|---|
| Responses 原生远程 MCP | OpenAI 服务访问公开的 MCP URL | 是 |
| 本地 stdio MCP 客户端 | 你的 Python 进程启动并连接本地服务 | 否 |
| 离线协议演示 | ScriptedClient 返回固定 MCP 输出项 | 是，明确标注模拟，不发网络请求 |

因此 `http://localhost:...` 不能作为“让 OpenAI 连接我本机”的地址。URL 必须指向 OpenAI 可访问、你有权使用的服务；你的 API Key 用来访问 OpenAI，不会自动成为远程 MCP 服务的登录凭证。

## 请求与输出字段

```python
tools = [{
    "type": "mcp",
    "server_label": "course_docs",
    "server_url": "https://your-mcp.example.com/mcp",
    "allowed_tools": ["search_docs"],
    "require_approval": "always",
}]
```

`search_docs` 只是本章模拟工具名；真实运行必须替换成你自己的服务实际公开的名称。`allowed_tools` 限制模型可见范围，`require_approval="always"` 要求每次工具调用先交给宿主审批。

| 输出类型 | 含义 | 宿主行为 |
|---|---|---|
| `mcp_list_tools` | 远程服务的工具信息 | 保留用于审计，不当成用户指令 |
| `mcp_approval_request` | 待批准的工具名和参数 | 显示 server_label、name、arguments，询问用户 |
| `mcp_call` | 调用结果或 error | 检查错误，保留真实结果 |
| `message` / `reasoning` | 模型回答或推理协议项 | 完整保留，不能只提取文本再丢弃其余项 |

批准后发送 `{"type":"mcp_approval_response","approval_request_id":请求id,"approve":true}`；拒绝则把 `approve` 设为 false。审批对象是审批请求 ID，不是某个 function call 的 call_id。

本章使用 `store=True` 与 `previous_response_id` 继续响应链。后续 `input` **仅包含新的审批结果**，不重复回传整段历史；本地另存全部 output 便于观察。每一轮重新发送 instructions 和 tools。普通章节的 `store=False` 手动历史模式与此不同，请不要混用导致重复上下文。本章主动启用响应存储，需按账户数据设置和官方保留说明理解其生命周期。

## 运行

```bash
python s14_mcp/code.py --demo
python s14_mcp/code.py --mcp-url https://YOUR-SERVICE/mcp --allowed-tool YOUR_TOOL
```

离线演示会显示“工具发现 → 审批请求 → 模拟批准 → 模拟结果”，不连接任何远程地址。真实模式需安装项目依赖、配置 `OPENAI_API_KEY`；也可在 `.env` 设置 `MCP_SERVER_URL`。终端显示真实审批参数后，仅输入 `y` 才批准当前请求；非交互终端默认拒绝。

为兼容统一课程入口，本章接受 `--workspace` 与 `--allow-write`，但不使用本地工作目录；`--allow-write` 不授予远程 MCP 调用权限，真实请求始终逐次审批。

远程工具可能读取或修改外部系统，参数会传给对应 MCP 服务。请用自己的测试服务和适当的工具白名单练习。本章没有配置 OAuth、authorization 字段或商业服务连接器；需要认证时，按官方方案在宿主扩展，不能把凭证塞进模型提示词或 URL。

## 推荐源码阅读与练习

1. [mcp.py](../harness/mcp.py) 的 `remote_mcp_tool()`：URL 与白名单要求。
2. `run_remote_mcp()`：完整 output 保存、审批分支和响应链。
3. [code.py](code.py) 的 `approve()`：真实与离线审批如何明确分开。

| 练习 | 验收 |
|---|---|
| 在模拟回调中返回 False | 下一请求为 approve=false，没有自动改为批准 |
| 一个响应返回两个审批请求 | 两个请求各自产生对应 approval_request_id |
| 返回 incomplete 且带审批项 | 不继续执行，报告未完成 |
| 返回 mcp_call.error | 不把工具失败报告成成功 |

当前循环最多 6 轮，不实现本地 stdio transport、OAuth、自动重连和 UI 审批队列。网络可访问性与服务工具名称必须由实际服务验证；离线测试只能验证协议分支，不能证明远程服务可用。

## 来源

- [OpenAI：Remote MCP tools](https://developers.openai.com/api/docs/guides/tools-remote-mcp)
- [OpenAI：Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI：Your data](https://developers.openai.com/api/docs/guides/your-data)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
