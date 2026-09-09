# s12：可重启的定时任务

后台任务回答“现在开始，稍后取结果”，定时任务回答“到某个时刻才允许开始”。本章把到期时间和动作参数写入 SQLite，让程序重启后仍能找回计划。

## 调度器由什么组成

| 部件 | 实现 | 设计原因 |
|---|---|---|
| 时间 | Unix 时间戳 `available_at` | 不依赖易丢失的内存倒计时 |
| 动作白名单 | `handlers={"format_note": handler}` | 模型不能存入任意代码等待未来执行 |
| 数据 | JSON 可序列化 payload | 重启后可以重建调用参数 |
| 扫描 | `run_due(owner, now, limit)` | 每批有上限，仅认领已到期任务 |
| 所有权 | 复用 TaskStore 租约 | 多执行者正常情况下不会同时认领 |
| 结果 | 成功、失败及具体结果写回数据库 | 重启后能解释任务为什么结束 |

`schedule_note` 只安排格式化字符串的本地工作，不发送邮件、不创建系统级提醒。`scheduler_run_due` 是实际执行入口。这个教学程序退出后不会继续运行，保存一个未来时间也不会自动启动操作系统守护进程。

## OpenAI 对应字段

模型通过 `function_call` 请求安排和扫描任务；宿主用 `function_call_output` 回传计划 ID、执行结果和当前状态。时间流逝与到期判定由 Python 宿主负责，不依赖模型“记得稍后再做”。

本章没有把整个 Responses 请求保存在数据库，也没有定时发送原始会话。持久化的是明确的动作名和输入。需要未来再调用模型时，应注册一个固定 handler，在该 handler 内重新构建预算、指令和权限。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 `handlers`：可执行动作由开发者预先登记。
2. [jobs.py](../harness/jobs.py) 的 `PersistentScheduler.schedule()`：动作如何落到任务表。
3. `run_due()`：认领 → 执行 → 写回三个阶段，以及异常如何记录。
4. [storage.py](../harness/storage.py) 的 `claim()`：时间门槛和租约回收。

## 运行

```bash
python s12_scheduler/code.py --demo
python s12_scheduler/code.py --workspace .workspaces --allow-write
```

离线演示安排一个立即到期任务，把 `hello scheduler` 变成 `HELLO SCHEDULER`。末尾重新打开数据库，已完成结果仍在；再次扫描的重复执行数应为 0。模型输出是脚本，时钟、动作、数据库和重启读取都真实运行。

真实数据库保存在 `s12/scheduler.sqlite3`。你可以通过 `--prompt` 让模型安排延迟任务，但程序不会为等待未来时间而阻塞。再次启动并要求执行已到期任务即可扫描；要持续运行需自行编写轮询进程，并为轮询和停机设置策略。

## 崩溃窗口为什么仍然存在

执行动作与保存“已完成”无法放进同一个普通数据库事务。例如外部服务已经接受请求，进程在写回结果前崩溃，租约到期后新执行者可能重复执行。这里提供的是可恢复认领，需要幂等动作；不能宣称任意副作用“恰好一次”。

| 练习 | 验收 |
|---|---|
| 指定测试时钟，在到期前后分别扫描 | 到期前不执行，到期后执行 |
| 创建任务后重新构造 scheduler | 相同数据库可找到相同任务 |
| 让一个 handler 抛错 | 数据库保存 failed 和错误原因 |
| 模拟副作用完成但未 ack 的崩溃 | 识别重复执行窗口，给动作增加幂等键 |

本实现为一次性时间戳调度，没有 cron 表达式、时区日历、周期展开、自动续租或补偿事务。处理耗时应短于租约。生产定时系统还需要处理时钟偏移、错过的调度点和进程退出恢复。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Responses API](https://developers.openai.com/api/reference/resources/responses)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
