import unittest

from preflight import assess


def make_record(answers, reward="₦50,000", deadline="2026-11-01"):
    return {
        "reward": reward,
        "deadline": deadline,
        "review_questions": [
            {"question": f"Check {i + 1}", "answer": answer}
            for i, answer in enumerate(answers)
        ],
    }


class PreflightAssessmentTests(unittest.TestCase):
    def test_unanswered_checks_require_review(self):
        result = assess(make_record(["verified", "unverified", "verified"]))
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["unanswered_checks"], 1)

    def test_blocked_check_blocks_opportunity(self):
        result = assess(make_record(["verified", "blocked", "unverified"]))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked_checks"], 1)

    def test_all_checks_reviewed_allows_human_review(self):
        result = assess(make_record(["verified"] * 5))
        self.assertEqual(result["status"], "ready_for_human_review")
        self.assertEqual(result["unanswered_checks"], 0)

    def test_missing_reward_prevents_ready_status(self):
        result = assess(make_record(["verified"] * 5, reward="Not recorded"))
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["missing_reward"])

    def test_missing_deadline_prevents_ready_status(self):
        result = assess(make_record(["verified"] * 5, deadline="Not yet verified"))
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["missing_deadline"])

    def test_empty_checklist_is_not_ready(self):
        result = assess(make_record([]))
        self.assertEqual(result["status"], "needs_review")

    def test_assessment_warns_about_external_verification(self):
        result = assess(make_record(["verified"] * 5))
        self.assertIn("does not independently", result["note"])


if __name__ == "__main__":
    unittest.main()
