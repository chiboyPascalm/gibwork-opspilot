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


if __name__ == "__main__":
    unittest.main()
