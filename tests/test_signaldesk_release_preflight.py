import unittest

from scripts.signaldesk_release_preflight import EXPECTED, evaluate_readiness


def good_rows():
    return [
        {"label": label, "http_status": 200, "cors": "PASS",
         "details": "Feed PASS: 30 Global / 10 India records, snapshot age 6 minutes"
         if label == "Preview live feed" else
         "Read-only collector contract verified"
         if label in ("Production health origin", "Preview health origin",
                      "Untrusted origin rejected") else
         "Archive endpoint returned HTTP 200 (data completeness not verified)"}
        for label in EXPECTED
    ]


class SignalDeskReleasePreflightTests(unittest.TestCase):
    def test_all_five_get_only_public_checks_needed(self):
        good = good_rows()
        self.assertEqual(evaluate_readiness(good), {"ready": True, "blockers": []})
        self.assertFalse(evaluate_readiness(good[:-1])["ready"])
        self.assertFalse(evaluate_readiness(None)["ready"])

    def test_preview_cors_failure_blocks_even_if_live_feed_returns_200(self):
        rows = good_rows()
        for row in rows:
            if row["label"] in ("Preview health origin", "Preview live feed",
                                "Untrusted origin rejected"):
                row["cors"] = "FAIL"
        decision = evaluate_readiness(rows)
        self.assertFalse(decision["ready"])
        self.assertIn("Preview live feed", decision["blockers"])
        self.assertIn("Untrusted origin rejected", decision["blockers"])

    def test_failed_health_and_stale_feed_block_despite_successful_http(self):
        rows = good_rows()
        for row in rows:
            if row["label"] == "Production health origin":
                row["details"] = "Health flags or deployed collector contract do not match current tested code"
            if row["label"] == "Preview live feed":
                row["details"] = "Feed FAIL: Snapshot age outside allowed range"
        decision = evaluate_readiness(rows)
        self.assertFalse(decision["ready"])
        self.assertIn("Production health origin", decision["blockers"])
        self.assertIn("Preview live feed", decision["blockers"])

    def test_network_failure_and_duplicate_results_do_not_pass(self):
        rows = good_rows()
        rows[0]["http_status"] = None
        self.assertFalse(evaluate_readiness(rows)["ready"])
        duplicate = good_rows()
        duplicate[-1] = duplicate[0]
        self.assertFalse(evaluate_readiness(duplicate)["ready"])


if __name__ == "__main__":
    unittest.main()
