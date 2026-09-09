"""s11：有界线程池、立即返回的任务句柄与显式结果读取。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import lesson_args, run_example
from harness.core import Tool, object_schema
from harness.fakes import call, reply, response
from harness.jobs import BackgroundJobs


def count_primes(upper):
    if not isinstance(upper, int) or not 2 <= upper <= 100_000:
        raise ValueError("upper 必须是 2–100000 的整数")
    count = 0
    for number in range(2, upper + 1):
        if all(number % divisor for divisor in range(2, int(number ** 0.5) + 1)):
            count += 1
    return {"upper": upper, "prime_count": count}


def main():
    args = lesson_args(__doc__)
    if args.demo:
        args.allow_write = True  # 本章状态只存在于内存中。
    with BackgroundJobs(max_workers=2, max_pending=4) as jobs:
        def submit(job_id, upper):
            if not 2 <= upper <= 100_000:
                raise ValueError("计算范围超出本章限制")
            jobs.submit(job_id, count_primes, upper)
            return {"job_id": job_id, "status": jobs.status(job_id)}

        tools = [
            Tool("job_submit", "提交素数统计，立即返回句柄", object_schema({
                "job_id": {"type": "string"}, "upper": {"type": "integer"}}),
                 submit, mutating=True),
            Tool("job_status", "查询后台任务状态", object_schema({"job_id": {"type": "string"}}),
                 lambda job_id: {"job_id": job_id, "status": jobs.status(job_id)}),
            Tool("job_result", "读取任务结果，最多等 2 秒；超时可以稍后重试",
                 object_schema({"job_id": {"type": "string"}}),
                 lambda job_id: {"result": jobs.result(job_id, timeout=2)}),
        ]
        scripted = [
            response(call("job_submit", {"job_id": "small", "upper": 1000}),
                     call("job_submit", {"job_id": "large", "upper": 10000}, "call_large")),
            response(call("job_status", {"job_id": "large"}, "call_status")),
            response(call("job_result", {"job_id": "small"}, "call_result_small"),
                     call("job_result", {"job_id": "large"}, "call_result_large")),
            response(reply("[模拟] 两个后台任务已返回结果：1000 以内有 168 个素数，10000 以内有 1229 个。")),
        ]
        run_example(tools, args.prompt or "并行提交统计 1000 和 10000 以内素数的任务，然后读取两份真实计算结果。",
                    scripted, args)


if __name__ == "__main__":
    main()
