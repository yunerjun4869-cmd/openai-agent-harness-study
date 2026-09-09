# 官方来源与参考说明

核对日期：2026-09-09 至 2026-09-10（北京时间）。链接指向持续更新的官方文档，
模型与 SDK 的实际可用性以账户和安装版本为准。本课程实测 SDK 为 openai 2.54.0。

| 来源 | 本课程用途 |
|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) | Responses 工具定义、strict schema、call_id、function_call_output 与多次调用 |
| [OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) | 完整历史回传、store、previous_response_id |
| [OpenAI Reasoning](https://developers.openai.com/api/docs/guides/reasoning) | 保留 reasoning 项、无状态加密内容、当前工具链的完整性 |
| [OpenAI MCP and Connectors](https://developers.openai.com/api/docs/guides/tools-remote-mcp) | 远程 MCP、allowed_tools、require_approval、审批请求与响应 |

实际读取了以上页面正文与 Markdown 版本后实现代码。SDK HTTP mock 测试用于验证
本地 SDK 的请求格式和响应解析，不能替代真实账户、模型与 MCP 服务的联网验证。

## 参考项目

[hubooooooo/claude-code-herness-study](https://github.com/hubooooooo/claude-code-herness-study)
提供了本课程的主题顺序参考；阅读时 main 提交为 `773e740e14af9df0b3ad7e5091c242bc414ef430`。
其开源许可证为 MIT。本版重新编写代码和中文讲义，没有把它的 Anthropic 运行时直接改名。
原项目的 MCP 演示使用进程内模拟服务，本版把离线模拟与真实 Responses 远程 MCP 接口分开。

## 编写原则

官方文档说明 API 协议；课程中的任务库、租约、权限策略和目标验收是教学实现的设计选择。
这些本地机制不能归因于 OpenAI API 自动提供，也不能当成官方 Codex 内部源码的准确还原。
