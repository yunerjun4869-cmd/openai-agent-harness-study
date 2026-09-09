# s03 · 权限：把执行许可放在模型外面

本章回答：模型说“我需要写文件”，是否就应该允许？执行器必须区分模型的请求和用户授予的能力。

## 机制与源码导读

`code.py` 注册与上一章相同的文件工具，请求写入 `learning.txt`。区别在于明确观察 `--allow-write` 对真实文件状态的影响。

| 层级 | 职责 | 阅读位置 |
|---|---|---|
| 模型 | 生成写文件参数 | 模拟响应中的 `write_file` |
| 工具定义 | 标记有副作用的能力 | `Tool.mutating` |
| 执行器 | 在 handler 运行前检查授权 | `ToolRegistry.execute` |
| CLI | 将人的命令行选择转为许可 | `lesson_args`、`run_example` |
| 文件系统 | 验证目标确实在工作目录内 | `Workspace.write_file` |

执行器拒绝时仍返回一个工具结果，让模型知道没有执行。`ok: false` 不等于“已写入但提醒一下”。最后程序额外打印文件是否存在，给学习者可见的独立证据。

## OpenAI 差异

OpenAI 工具定义中的 `strict: true` 约束参数结构，**不授予本地执行权限**。函数调用输出里的工具名和内容都需要执行器检查。本课程的 `mutating` 是本地属性，不会作为自造字段发送到 OpenAI API。

如果业务需要逐操作审批，可使用 `ToolRegistry(..., approve=callback)`。回调接收 `(tool, args)` 并返回布尔值；审批依据应来自真实用户或应用策略，不能调用同一个模型询问它是否同意自己执行。

## 运行与预期

```bash
python s03_permission/code.py --demo
python s03_permission/code.py --demo --allow-write
python s03_permission/code.py --workspace ./study_data --allow-write
```

前两次均为模拟 LLM、真实本地工具。在临时目录中，第一次预期写入被拒绝且文件不存在；第二次预期文件存在。第三次为真实 API 调用，在指定目录写入，需要已设置 `OPENAI_API_KEY`。默认模型 `gpt-6-astra`，使用 `OPENAI_MODEL` 修改。

## 改进与边界

默认不授予修改权限，使学习者能先理解工具调用再打开副作用。权限检查和工具参数验证都在 handler 之前完成。即使提示词中出现“忽略规则、立即写入”，模型输出也无法直接绕过执行器。

`--allow-write` 是这个教学进程的宽泛写许可。它不是完善的企业权限系统，也不等于对所有外部操作的授权。生产系统需要按工具、目标路径、动作类型和租户缩小许可；审批后仍需重新验证操作对象。

## 练习

1. 增加只允许 `notes/` 下写入的审批回调，观察合法与非法目标。
2. 编写 handler 计数器，断言拒绝操作时 handler 从未运行。
3. 思考“删除”“发送消息”“部署”是否应该共享同一个写权限开关。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [安全最佳实践](https://developers.openai.com/api/docs/guides/safety-best-practices)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。本课程采用本地强制校验的权限机制。
