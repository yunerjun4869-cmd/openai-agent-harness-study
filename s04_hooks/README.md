# s04 · Hooks：观察和约束每一次工具执行

本章回答：如何给所有工具统一增加审计、延时统计和策略检查，而不用修改每个业务函数？

## 机制与源码导读

`AuditHook` 是一个实现 `__call__(event, payload)` 的对象。注册到 `ToolRegistry(hooks=[audit])` 后，会在工具执行过程中收到事件。

| 事件 | 可做的事 | 注意点 |
|---|---|---|
| `before` | 开始计时、检查策略 | 抛错会阻止工具运行 |
| `after` | 记录耗时、成功统计 | 不能撤销已经发生的副作用 |
| `denied` | 统计权限拒绝 | 工具 handler 没有运行 |
| `error` | 记录校验或执行失败 | 错误日志也可能含敏感信息 |

`code.py` 用一个词数统计工具，直接构造 `ResponsesAgent`，让读者看到 hook 注入位置。继续阅读 `harness/tools.py` 的事件派发和异常处理：观察能力应与工具执行职责分离。

审计只记录事件名、工具名和耗时，不复制输入文本。实际系统可追加应用生成的请求 id、租户 id 和脱敏后的错误类型。

## OpenAI 差异

本章 hooks 属于本地 Python harness，OpenAI Responses API 不会替你执行它们。API 的函数工具 schema 继续保持原样；运行前后的动作都发生在 `function_call` 和 `function_call_output` 之间。

完整响应历史用于模型继续推理，审计记录用于运维和核验。二者用途不同，不能为了“方便排查”无条件把全部历史、API Key 或工具原始参数写入日志。

## 运行与预期

```bash
python s04_hooks/code.py --demo
python s04_hooks/code.py --prompt "调用工具统计 reliable agents need logs 的词数"
```

第一条命令不调用 API，预期打印 `before`、`after` 两个审计事件以及词数 3。第二条调用真实 API，需要 `OPENAI_API_KEY`，默认模型是 `gpt-6-astra`，可通过 `OPENAI_MODEL` 修改。

计时由本地 `monotonic()` 得出，避免系统时钟回拨影响耗时。演示中的统计是本地工具执行耗时，不包含完整模型网络延迟。

## 改进、练习与边界

执行前 hook 失败时拒绝继续运行；执行后 hook 失败时保留真实工具结果并记录诊断，避免日志故障让模型误以为有副作用的工具从未执行。

1. 增加一个 `before` hook，禁止超过阈值的操作，测试 handler 未执行。
2. 让 `after` hook 故意报错，检查结果是否仍如实反映工具执行情况。
3. 将内存日志改为 JSON Lines，并明确脱敏规则、轮转和保留周期。

本章 `started` 以工具名称索引，只适用于课程的串行执行器。并行执行同名工具时，应由执行器提供独立执行 id，再用该 id 关联前后事件。审计 hook 不是事务回滚机制。

官方阅读：[函数调用生命周期](https://developers.openai.com/api/docs/guides/function-calling) · [生产最佳实践](https://developers.openai.com/api/docs/guides/production-best-practices)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。本章重新实现有明确失败语义的工具钩子。
