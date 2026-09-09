"""由应用预设验收器驱动的有界目标循环；模型文字不参与完成判断。"""

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    passed: bool
    source: str
    details: dict


@dataclass
class GoalResult:
    status: str
    rounds: int
    evidence: list[Evidence] = field(default_factory=list)
    error: str | None = None


class GoalLoop:
    """验收器属于可信应用代码，应根据工具退出码与具体断言生成证据。"""

    def __init__(self, max_rounds=3):
        if type(max_rounds) is not int or max_rounds < 1:
            raise ValueError("目标循环轮数必须为正整数")
        self.max_rounds = max_rounds

    def run(self, attempt, verify):
        """attempt(round_number) 执行动作；verify() 返回 Evidence。

        证据类型本身无法认证工具来源。应用必须固定验收器，不能让模型
        提供 passed 字段或改写验收器。本模块只限制轮数，不强制终止回调；
        模型调用和工具执行应分别设置超时与调用预算。
        """
        evidence = []
        for round_number in range(1, self.max_rounds + 1):
            try:
                attempt(round_number)
                result = verify()
                if (not isinstance(result, Evidence) or type(result.passed) is not bool
                        or not isinstance(result.source, str) or not result.source.strip()
                        or not isinstance(result.details, dict)):
                    raise TypeError("验收器必须返回含布尔结论、工具来源和详情的 Evidence")
                evidence.append(deepcopy(result))
                if result.passed:
                    return GoalResult("completed", round_number, evidence)
            except Exception as exc:
                return GoalResult("failed", round_number, evidence, f"{type(exc).__name__}: {exc}")
        return GoalResult("budget_exceeded", self.max_rounds, evidence)
