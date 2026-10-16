import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import gibwork_integration


class GibworkIntegrationTests(unittest.TestCase):
    @patch("gibwork_integration.shutil.which", return_value="/usr/bin/npx")
    @patch("gibwork_integration.subprocess.run")
    def test_live_success_uses_read_only_discovery(self, run, _which):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"ok": True, "tasks": []}),
            stderr="",
        )

        result = gibwork_integration.discover_tasks(2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "live_cli")
        self.assertEqual(result["result"], {"ok": True, "tasks": []})
        command = run.call_args.args[0]
        self.assertIn("available", command)
        self.assertNotIn("create", command)
        self.assertNotIn("refund", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 45)

    @patch("gibwork_integration.shutil.which", return_value="/usr/bin/npx")
    @patch("gibwork_integration.subprocess.run")
    def test_missing_wallet_is_reported_safely(self, run, _which):
        run.return_value = SimpleNamespace(
            returncode=1,
            stdout=json.dumps({
                "ok": False,
                "error": {
                    "code": "CREDENTIAL_ERROR",
                    "message": "No wallet configured.",
                },
            }),
            stderr="",
        )

        result = gibwork_integration.discover_tasks()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "CREDENTIAL_ERROR")
        self.assertIn("No Gibwork wallet is configured", result["error"]["message"])

    @patch("gibwork_integration.shutil.which", return_value="/usr/bin/npx")
    @patch("gibwork_integration.subprocess.run")
    def test_invalid_json_is_handled(self, run, _which):
        run.return_value = SimpleNamespace(
            returncode=0, stdout="not json", stderr=""
        )

        result = gibwork_integration.discover_tasks()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "INVALID_RESPONSE")

    def test_bad_limit_does_not_run_cli(self):
        with patch("gibwork_integration.subprocess.run") as run:
            result = gibwork_integration.discover_tasks(101)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "INVALID_LIMIT")
        run.assert_not_called()

    def test_demo_is_clearly_labelled_and_offline(self):
        result = gibwork_integration.offline_demo()
        self.assertEqual(result["mode"], "offline_demo")
        self.assertIn("SAMPLE DATA ONLY", result["notice"])
        self.assertIn("SAMPLE ONLY", result["sample_task"]["title"])


if __name__ == "__main__":
    unittest.main()
