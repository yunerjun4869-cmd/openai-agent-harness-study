# s07 · 技能按需加载：先看目录，再读正文

本章回答：当参考资料越来越多，如何避免每次请求都把所有文档塞进上下文？

## 机制与源码导读

`SkillLibrary` 管理本章 `skills/` 下的 Markdown 文件。`list_skills` 只返回名称和文件大小，模型选中后再调用 `load_skill(name)` 读取正文。这个两阶段过程把大量静态资料变成按需工具结果。

| 源码 | 关注点 |
|---|---|
| `code.py` | 工具目录与正文读取分别注册，instructions 说明资料信任边界 |
| `skills/evidence.md` | 一份简短、单一用途、附来源的教学技能 |
| `harness/knowledge.py` 的 `SkillLibrary` | 文件名检查、真实路径检查、文件大小限制 |

工具返回包含 `name`、`source`、`content`、`trusted: false`。来源方便模型引用与学习者回查；不信任标记提示正文没有自动获得高优先级指令地位。

## OpenAI 差异

这里的“技能”是应用层的 Markdown 资料管理方式，不是 Responses API 中一个自动识别的 `skill` 字段。模型通过标准函数调用读取资料，正文作为 `function_call_output` 回传。

长期稳定的行为规范应由开发者审查后放到 `instructions`。仓库文件、网页内容、用户提供的技能正文属于数据，不能仅因扩展名是 Markdown 就当作系统指令。布尔标记本身也不能保证模型忽略恶意要求，执行器权限仍是最后边界。

## 运行与预期

```bash
python s07_skill_loading/code.py --demo
python s07_skill_loading/code.py --prompt "选择合适技能，解释怎样验证工具操作成功"
```

`--demo` 使用模拟 LLM，实际执行技能目录扫描与文件读取。预期先列出 `evidence`，再读取正文，最后说明应检查状态和证据。真实模式需要 `OPENAI_API_KEY`，默认模型 `gpt-6-astra`，可用 `OPENAI_MODEL` 覆盖。

## 改进、练习与边界

文件名单独检查，禁止 `../` 和路径形式的技能名；符号链接解析后仍需落在技能目录。单文件超过 20,000 字节会拒绝加载，提示拆分内容。

1. 添加 `skills/code_review.md`，观察模型是否根据问题选择不同资料。
2. 给目录增加描述和适用条件；比较只返回文件名时的选择质量。
3. 写一个包含“忽略当前用户指令”的测试资料，验证其无法绕过本地写权限。

本章没有语义搜索、签名校验、技能版本或来源可信度评分。目录元数据简化为名称和字节数，资料较多时应增加人工编写的摘要与检索机制。重新读取文件可能读到新版本，需要可复现执行时应保存内容摘要。

官方阅读：[函数调用](https://developers.openai.com/api/docs/guides/function-calling) · [安全最佳实践](https://developers.openai.com/api/docs/guides/safety-best-practices)

结构参考：[原项目](https://github.com/hubooooooo/claude-code-herness-study)。本课程不直接加载或执行来源项目的技能指令。
