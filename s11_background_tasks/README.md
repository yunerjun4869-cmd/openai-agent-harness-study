# s11：后台任务与有界并发

工具调用通常是同步的：宿主执行完工具，才能把结果发回模型。如果一项工作较慢，模型会停在等待处。本章把“提交任务”和“获取结果”拆开，用任务 ID 连接这两个时刻。

## 从函数返回值变成任务句柄

| 时刻 | 工具 | 宿主动作 | 模型能知道什么 |
|---|---|---|---|
| 提交 | `job_submit(job_id, upper)` | 把固定的素数统计函数提交到线程池 | 任务已接受，尚不能声称计算完成 |
| 查询 | `job_status(job_id)` | 读取 Future 状态 | pending / running / completed / failed |
| 取结果 | `job_result(job_id)` | 最多等待 2 秒并返回实际结果 | 计算值或明确错误 |

线程池最多同时运行 2 个任务，总共允许 4 个未完成任务。队列满时提交失败，把压力暴露给调用方。不能无限增加线程和待执行列表，否则模型一次计划过多工作就可能耗尽资源。

模型有时会在一个响应中产生多次工具调用。基础循环按顺序处理这些调用；这里提交动作很快返回，真正的工作在后台线程中重叠进行。这两种并发层次需要分开理解。

## OpenAI 对应字段

每次提交、查询、取结果仍是普通 function calling，每次有独立 `call_id`。后台任务使用宿主生成或校验的 `job_id`，它不是 `call_id`，也不是 Responses 的 `response.id`。

| 标识 | 生命周期 | 用途 |
|---|---|---|
| `call_id` | 一次模型工具调用 | 配对 `function_call_output` |
| `job_id` | 从提交直到结果释放 | 多次查询同一个后台工作 |
| `response.id` | 一个模型响应 | 标识 OpenAI 返回的响应对象 |

OpenAI 的 `background=true` 是“让模型响应异步生成”的另一项 API 能力。本章没有使用该选项；这里运行的是宿主 Python 后台工具。两者可以组合，但不能把本地线程称为 OpenAI 后台响应服务。

## 推荐源码阅读顺序

1. [code.py](code.py) 的 `count_primes()`：工作函数有明确输入上限，不接受任意 Python 或 Shell。
2. [jobs.py](../harness/jobs.py) 的 `submit()`：锁保护重复 ID、容量和 Future 表。
3. `status()` 与 `result()`：失败状态以及原始异常如何传给调用方。
4. `close()`：退出上下文时等待已提交任务结束。

## 运行

```bash
python s11_background_tasks/code.py --demo
python s11_background_tasks/code.py --allow-write
```

在 `openai` 目录运行。离线模式的模型回复来自脚本，素数计算真实执行：1000 以内有 168 个，10000 以内有 1229 个。计算较快，首次查询可能已经是 `completed`，这不表示线程池失效。

真实模式需要 OpenAI 配置。`job_submit` 作为启动工作和修改任务状态的操作需要授权；状态查询和结果读取不需要写权限。

## 练习与判断标准

| 练习 | 观察 |
|---|---|
| 在测试中用事件阻塞 worker，再连续提交 | 达到容量上限后拒绝新任务 |
| 提交会抛异常的固定函数 | `status` 为 failed，`result` 抛出同一类型异常 |
| 对未完成任务调用很短的 result timeout | 等待超时，但工作线程仍在运行 |
| 读取结束后调用 `forget(job_id)` | 已完成结果从内存释放 |

Python 线程不能被可靠地强制终止，`result(timeout=...)` 只限制调用方等待时间。本例工作量有界；面向任意外部命令应使用可终止的子进程、容器或任务服务。CPU 密集任务受 GIL 限制，示例主要用于观察调度；生产计算可使用进程池。

这些 Future 和结果只存在于当前进程，重启会丢失。下章把可恢复的任务状态加入调度器。外部副作用的重试还需要幂等键，不能靠 `job_id` 自动获得“恰好执行一次”。

## 来源

- [OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI：Background mode](https://developers.openai.com/api/docs/guides/background)
- [原项目结构参考](https://github.com/hubooooooo/claude-code-herness-study)
