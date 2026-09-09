"""模型自报成功不能替代工具证据；失败与预算准确退出。"""

import unittest

from harness.goal import Evidence, GoalLoop


class GoalTests(unittest.TestCase):
    def test_model_claim_is_ignored_until_tool_assertion_passes(self):
        state = {"attempts": 0}

        def attempt(round_number):
            state["attempts"] = round_number
            return "已完成，所有测试通过"

        def verify():
            tool_result = {"exit_code": 0 if state["attempts"] >= 2 else 1, "checks": 3}
            return Evidence(tool_result["exit_code"] == 0 and tool_result["checks"] > 0,
                            "run_checks", tool_result)

        result = GoalLoop(max_rounds=3).run(attempt, verify)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.rounds, 2)
        self.assertEqual([e.passed for e in result.evidence], [False, True])

    def test_failed_evidence_exhausts_exact_round_budget(self):
        attempts = []
        result = GoalLoop(max_rounds=2).run(
            attempts.append, lambda: Evidence(False, "run_checks", {"exit_code": 1}))
        self.assertEqual(attempts, [1, 2])
        self.assertEqual(result.status, "budget_exceeded")
        self.assertEqual(len(result.evidence), 2)

    def test_plain_bool_or_string_passed_is_not_evidence(self):
        for invalid in (True, {"passed": True}, Evidence("true", "tool", {})):
            result = GoalLoop().run(lambda _: "完成", lambda: invalid)
            self.assertEqual(result.status, "failed")
            self.assertIn("TypeError", result.error)

    def test_verifier_exception_does_not_report_completion(self):
        def verify():
            raise OSError("检查工具不可用")

        result = GoalLoop().run(lambda _: None, verify)
        self.assertEqual(result.status, "failed")
        self.assertIn("OSError", result.error)
        self.assertEqual(result.rounds, 1)

    def test_evidence_history_is_snapshot(self):
        details = {"count": 0}

        def verify():
            details["count"] += 1
            return Evidence(False, "run_checks", details)

        result = GoalLoop(max_rounds=2).run(lambda _: None, verify)
        self.assertEqual([e.details["count"] for e in result.evidence], [1, 2])


if __name__ == "__main__":
    unittest.main()
