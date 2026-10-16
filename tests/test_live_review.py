import unittest

from live_review import review_task, build_report, analyze_reward


class LiveReviewTests(unittest.TestCase):
    def test_zero_slots_blocks_listing(self):
        result = review_task({
            "id": "task-1",
            "title": "Full listing",
            "open": True,
            "slots_remaining": 0,
        })

        self.assertEqual(result["status"], "blocked_by_listing")
        self.assertTrue(any(
            "slots remain" in item for item in result["blockers"]
        ))

    def test_unknown_slots_requires_manual_check(self):
        result = review_task({
            "id": "task-2",
            "title": "Unknown availability",
            "open": True,
            "slots_remaining": None,
        })

        self.assertEqual(result["status"], "needs_human_review")
        self.assertTrue(any(
            "Confirm available submission slots" in item
            for item in result["checks"]
        ))

    def test_closed_listing_is_blocked(self):
        result = review_task({
            "id": "task-3",
            "title": "Closed listing",
            "open": False,
            "slots_remaining": 5,
        })

        self.assertEqual(result["status"], "blocked_by_listing")
        self.assertIn("Listing is not open.", result["blockers"])

    def test_expired_deadline_is_blocked(self):
        result = review_task({
            "id": "task-4",
            "title": "Expired listing",
            "open": True,
            "slots_remaining": 5,
            "deadline": "2000-01-01T00:00:00Z",
        })

        self.assertEqual(result["status"], "blocked_by_listing")
        self.assertTrue(any(
            "deadline has passed" in item for item in result["blockers"]
        ))

    def test_premium_and_follower_requirements_are_reported(self):
        result = review_task({
            "id": "task-5",
            "title": "Restricted listing",
            "open": True,
            "slots_remaining": 5,
            "requires_premium": True,
            "minimum_twitter_followers": 800,
            "deadline": "2999-01-01T00:00:00Z",
        })

        self.assertEqual(result["status"], "needs_human_review")
        self.assertTrue(any(
            "Premium access" in item for item in result["checks"]
        ))
        self.assertTrue(any(
            "800-follower minimum" in item for item in result["checks"]
        ))

    def test_missing_deadline_requires_manual_check(self):
        result = review_task({
            "id": "task-6",
            "title": "No deadline",
            "open": True,
            "slots_remaining": 5,
        })

        self.assertTrue(any(
            "No deadline listed" in item for item in result["checks"]
        ))

    def test_invalid_deadline_does_not_crash(self):
        result = review_task({
            "id": "task-7",
            "title": "Invalid deadline",
            "open": True,
            "slots_remaining": 5,
            "deadline": "not-a-date",
        })

        self.assertEqual(result["status"], "needs_human_review")
        self.assertTrue(any(
            "Check the deadline directly" in item
            for item in result["checks"]
        ))


    def test_reward_extraction_avoids_inventing_individual_reward(self):
        result = analyze_reward(
            "Task pool is 100 USDC. Check the rules before participating."
        )
        self.assertEqual(
            result["advertised_reward"],
            "Individual reward not established from description",
        )

    def test_explicit_reward_is_flagged_for_verification(self):
        result = analyze_reward(
            "The base reward is $25. Earn $1.50 per 1,000 video views."
        )
        self.assertIn("$25 base reward", result["advertised_reward"])
        self.assertEqual(
            result["advertised_reward"].count("performance-based"), 1
        )

    def test_report_flags_similar_titles_without_removing_listings(self):
        report = build_report([
            {"id": "a", "title": "Create a Gibwork Mobile App Thread",
             "open": True, "slots_remaining": 3, "description": ""},
            {"id": "b", "title": "Create a Gibwork Mobile App Thread!",
             "open": True, "slots_remaining": 2, "description": ""},
        ], "production")
        self.assertEqual(report["count"], 2)
        self.assertTrue(any(
            task["possible_duplicates"] for task in report["tasks"]
        ))

    def test_priority_and_review_rank_are_present(self):
        report = build_report([
            {"id": "a", "title": "Unknown slots", "open": True,
             "slots_remaining": None, "description": ""},
            {"id": "b", "title": "Available listing", "open": True,
             "slots_remaining": 3, "description": "",
             "deadline": "2999-01-01T00:00:00Z"},
        ], "production")
        for task in report["tasks"]:
            self.assertIn("priority_score", task)
            self.assertIn("priority_reasons", task)
            self.assertIn("review_rank", task)
        self.assertEqual(
            sorted(task["review_rank"] for task in report["tasks"]), [1, 2]
        )


if __name__ == "__main__":
    unittest.main()
