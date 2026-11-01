import io
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.signaldesk_cloudflare_readonly import (
    BASE, ROUTES, SCRIPT, cloudflare_get, evaluate_inventory
)

DEPLOYMENT = "182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e"
VERSION = "023e105f-2a42-4f8b-a1c1-73f6a2a30c0f"
NAMESPACE = "a" * 32
ACCOUNT = "b" * 32


def good_parts():
    return {
        "settings": {"bindings": [
            {"type": "kv_namespace", "name": "NEWS_CACHE", "namespace_id": NAMESPACE}
        ]},
        "schedules": {"schedules": [{"cron": "*/15 * * * *"}]},
        "subdomain": {"enabled": True, "previews_enabled": False},
        "deployments": {"deployments": [
            {"id": DEPLOYMENT, "created_on": "2026-10-31T10:00:00Z",
             "versions": [{"version_id": VERSION, "percentage": 100}]}
        ]},
    }


class Response:
    def __init__(self, body):
        self.buf = io.BytesIO(json.dumps(body).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.buf.read(size)


class ReadOnlyCloudflareInventoryTests(unittest.TestCase):
    def test_exact_dedicated_worker_passes_but_does_not_authorize_deploy(self):
        report = evaluate_inventory(good_parts())
        self.assertTrue(report["inventory_pass"], report)
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["production_change_authorized"])
        self.assertEqual(report["worker"], SCRIPT)
        self.assertEqual(report["rollback_candidate"]["previous_version_id"], VERSION)
        self.assertNotIn(NAMESPACE, str(report))
        self.assertNotIn(ACCOUNT, str(report))

    def test_missing_or_ambiguous_kv_fails_closed(self):
        for bindings in ([], [{"name": "NEWS_CACHE", "type": "secret_text"}],
                         [{"name": "OTHER", "type": "kv_namespace", "namespace_id": NAMESPACE}],
                         good_parts()["settings"]["bindings"] * 2,
                         good_parts()["settings"]["bindings"] + [{"name": "EXTRA", "type": "secret_text"}]):
            with self.subTest(bindings=bindings):
                parts = good_parts()
                parts["settings"]["bindings"] = bindings
                self.assertFalse(evaluate_inventory(parts)["inventory_pass"])

    def test_wrong_schedule_or_missing_workers_dev_is_blocked(self):
        for crons in ([], [{"cron": "0 * * * *"}], [
            {"cron": "*/15 * * * *"}, {"cron": "0 * * * *"}]):
            parts = good_parts()
            parts["schedules"]["schedules"] = crons
            self.assertFalse(evaluate_inventory(parts)["inventory_pass"])
        parts = good_parts()
        parts["subdomain"]["enabled"] = False
        self.assertFalse(evaluate_inventory(parts)["inventory_pass"])

    def test_rollback_only_from_single_100_percent_live_version(self):
        for deployments in ([], [
            {"id": DEPLOYMENT, "created_on": "2026-10-31T10:00:00Z",
             "versions": [{"version_id": VERSION, "percentage": 60},
                          {"version_id": "1b2d4567-89ac-4fee-9dcd-0b6b0392c346",
                           "percentage": 40}]}], [
            {"id": "bad", "versions": [{"version_id": VERSION, "percentage": 100}]}]):
            parts = good_parts()
            parts["deployments"]["deployments"] = deployments
            self.assertFalse(evaluate_inventory(parts)["inventory_pass"])
            self.assertIsNone(evaluate_inventory(parts)["rollback_candidate"])

    def test_missing_api_metadata_is_never_assumed_healthy(self):
        for key in ROUTES:
            with self.subTest(endpoint=key):
                parts = good_parts()
                del parts[key]
                self.assertFalse(evaluate_inventory(parts)["inventory_pass"])

    def test_network_can_only_issue_a_single_allowlisted_get_to_exact_script(self):
        calls = []

        def fake_open(request, timeout):
            calls.append((request.full_url, request.get_method(), timeout))
            return Response({"success": True, "result": good_parts()["schedules"]})

        with patch("urllib.request.urlopen", fake_open):
            result = cloudflare_get("schedules", account_id=ACCOUNT, token="sensitive")
        self.assertEqual(result, good_parts()["schedules"])
        self.assertEqual(calls, [(BASE + "/accounts/" + ACCOUNT + ROUTES["schedules"], "GET", 12)])
        self.assertNotIn("sensitive", str(calls))
        with patch("urllib.request.urlopen", side_effect=AssertionError("must not call")):
            with self.assertRaises(ValueError):
                cloudflare_get("../workers/deploy", account_id=ACCOUNT, token="sensitive")
            with self.assertRaises(ValueError):
                cloudflare_get("schedules", account_id="bad", token="sensitive")
            with self.assertRaises(ValueError):
                cloudflare_get("schedules", account_id=ACCOUNT, token="")

    def test_inventory_workflow_is_manual_only_and_does_not_unlock_legacy_deployer(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/signaldesk-cloudflare-readonly-inventory.yml").read_text()
        legacy = (root / ".github/workflows/deploy-news-collector.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("if: github.repository == 'chiru52/x-news-automation'", workflow)
        self.assertIn("SIGNALDESK_CLOUDFLARE_READ_TOKEN", workflow)
        self.assertNotIn("cloudflare/wrangler-action", workflow)
        self.assertNotIn("setup_cloudflare.py", workflow)
        self.assertNotIn("gh workflow run", workflow)
        self.assertIn("if: github.repository == 'varadachiru/x-news-automation'", legacy)


if __name__ == "__main__":
    unittest.main()
