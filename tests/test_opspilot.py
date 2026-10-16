import opspilot
from unittest.mock import patch
import io
import contextlib
import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "opspilot.py"


class OpsPilotTests(unittest.TestCase):
    def run_app(self, home, *args):
        return subprocess.run(
            [sys.executable, str(home / "opspilot.py"), *args],
            cwd=home,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def test_local_task_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "opspilot.py").write_bytes(APP.read_bytes())

            added = self.run_app(
                home, "add", "Test task", "--notes", "Test notes"
            )
            self.assertIn("Added local task #1", added)

            listed = self.run_app(home, "list")
            self.assertIn("Test task", listed)
            self.assertIn("Test notes", listed)

            records = json.loads(
                (home / "data" / "tasks.json").read_text()
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "open")

            report = self.run_app(home, "report")
            self.assertIn("Markdown report:", report)
            self.assertIn("JSON report:", report)

            report_files = list((home / "reports").glob("report-*.json"))
            self.assertEqual(len(report_files), 1)
            payload = json.loads(report_files[0].read_text())
            self.assertEqual(payload["total_tasks"], 1)
            self.assertEqual(payload["tasks"][0]["title"], "Test task")


    def test_sync_imports_tasks_and_skips_invalid_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            tasks_path = data / "tasks.json"
            tasks_path.write_text(json.dumps([
                {"id": 1, "title": "My local task",
                 "status": "open", "source": "local"}
            ]))

            result = {
                "ok": True,
                "tasks": [
                    {"id": "task-1", "title": "New listing",
                     "open": True, "description": "Review the task"},
                    None,
                    {"title": "Missing external ID"},
                    {"id": "task-1", "title": "Repeated listing",
                     "open": True},
                ],
            }

            output = io.StringIO()
            with (
                patch.object(opspilot, "DATA", data),
                patch.object(opspilot, "TASKS", tasks_path),
                patch(
                    "gibwork_integration.discover_tasks",
                    return_value=result,
                ),
                contextlib.redirect_stdout(output),
            ):
                opspilot.cmd_sync(
                    argparse.Namespace(limit=5, environment="stage")
                )

            saved = json.loads(tasks_path.read_text())
            self.assertEqual(len(saved), 2)
            self.assertEqual(saved[0]["title"], "My local task")
            self.assertEqual(saved[1]["external_id"], "task-1")
            self.assertEqual(saved[1]["status"], "open")
            self.assertIn("Imported:    1", output.getvalue())
            self.assertIn("Skipped:     3", output.getvalue())

    def test_sync_second_run_does_not_duplicate_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            tasks_path = data / "tasks.json"
            result = {
                "ok": True,
                "tasks": [
                    {"id": "task-1", "title": "Same listing", "open": True}
                ],
            }

            with (
                patch.object(opspilot, "DATA", data),
                patch.object(opspilot, "TASKS", tasks_path),
                patch(
                    "gibwork_integration.discover_tasks",
                    return_value=result,
                ),
            ):
                args = argparse.Namespace(limit=5, environment="stage")
                opspilot.cmd_sync(args)
                opspilot.cmd_sync(args)

            saved = json.loads(tasks_path.read_text())
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["external_id"], "task-1")

    def test_sync_failure_does_not_change_saved_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            tasks_path = data / "tasks.json"
            original = json.dumps([
                {"id": 1, "title": "Keep this", "source": "local"}
            ])
            tasks_path.write_text(original, encoding="utf-8")

            with (
                patch.object(opspilot, "DATA", data),
                patch.object(opspilot, "TASKS", tasks_path),
                patch(
                    "gibwork_integration.discover_tasks",
                    return_value={
                        "ok": False,
                        "error": {
                            "code": "TEST_FAILURE",
                            "message": "Simulated discovery failure",
                        },
                    },
                ),
            ):
                with self.assertRaises(SystemExit):
                    opspilot.cmd_sync(
                        argparse.Namespace(
                            limit=5, environment="stage"
                        )
                    )

            self.assertEqual(
                tasks_path.read_text(encoding="utf-8"), original
            )


if __name__ == "__main__":
    unittest.main()
