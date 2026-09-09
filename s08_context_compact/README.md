# s08 · 上下文预算：按完整轮次裁剪，承认信息损失

本章回答：当历史越来越长，怎样缩短请求而不把 OpenAI 的工具调用协议破坏掉？

## 机制与源码导读

`compact_history` 用用户消息标识一个新轮次，按时间顺序删除最旧的完整轮次，直到满足本地字符预算。最新用户消息及其后的所有输出始终整体保留；开头位于首条用户消息之前的固定上下文也保留。

| 情形 | 处理 |
|---|---|
| 历史已经在预算内 | 原样返回一份列表副本 |
| 删除最旧完整轮次后够用 | 返回剩余历史与删除数量 |
| 当前轮次本身超过预算 | 抛出 `ContextOverflow`，要求明确开始新会话 |
| 超预算但没有用户边界 | 拒绝猜测可删位置 |

先读 `harness/context.py` 的轮次划分，再读 `code.py`：运行首轮，提前把下一条用户消息纳入预算，裁剪后续跑。`RunResult.history` 包含真实响应输出，不能简单只保留最后几条文本消息。

## OpenAI 差异

Responses 输出可能包括 `reasoning`、`function_call`、assistant message 等多种项目。应原样保留完整 `response.output`，并把 `function_call_output` 和对应调用一起传回。随意按消息条数截断，可能留下孤立的结果或丢失继续推理所需项目。

本课程主循环采用 `store=False`、手动传递历史。当前官方推理指南说明：这种模式默认返回加密的推理内容，无需额外指定 `include=["reasoning.encrypted_content"]`。加密内容是需要原样携带的 opaque 数据，不应该尝试解析或改写。

本章实现的是**有信息损失的应用层历史裁剪**。它不调用 OpenAI 的原生上下文压缩接口，也不生成能够保留所有信息的摘要。模型丢失旧结论后，可能需要重新读取文件或记忆。

## 运行与预期

```bash
python s08_context_compact/code.py --demo
python s08_context_compact/code.py
```

离线演示在第一条模拟用户消息中附加冗长背景，使历史超过 3,000 字符；随后添加新问题并裁掉整个旧轮次。程序打印裁剪前后字符数和删除数量，再调用工具重新获取课程要点。LLM 响应是脚本模拟，裁剪与工具函数真实运行。

真实模式需要 `OPENAI_API_KEY`，默认模型 `gpt-6-astra`，可通过 `OPENAI_MODEL` 修改。真实模式不注入冗长模拟背景，因此可能无需删除历史，这是正常现象。

## 改进、练习与边界

1. 构造包含 reasoning、函数调用、函数结果的最新轮次，确认裁剪保留完整链。
2. 将当前轮次做得比预算更大，检查明确失败而不是截断工具返回。
3. 引入摘要时记录被摘要范围和来源，比较“压缩事实”和“遗漏事实”的影响。

字符数不是 token 数；不同语言、schema、图片和加密推理内容的成本不同。本章阈值是教学用的保守应用限额，不能精确预测 API 上下文上限。真正的长任务还需要 token 监控、检索、分段处理和可恢复的任务状态。

官方阅读：[推理模型与手动历史](https://developers.openai.com/api/docs/guides/reasoning) · [对话状态](https://developers.openai.com/api/docs/guides/conversation-state) · [函数调用](https://developers.openai.com/api/docs/guides/function-calling)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。裁剪规则针对 Responses 输出协议重新设计。
