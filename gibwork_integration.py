#!/usr/bin/env python3
"""Safe, read-only integration with the Gibwork CLI."""

import argparse
import json
import os
import shutil
import subprocess
from html import unescape
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def plain_text(value):
    if not isinstance(value, str):
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        return unescape(parser.text())
    except Exception:
        return unescape(value)


def summarize_tasks(payload):
    """Summarize API task fields without guessing reward amounts."""
    if not isinstance(payload, dict):
        return []

    data = payload.get("data", payload)
    if isinstance(data, dict):
        items = data.get("results", data.get("tasks", []))
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if not isinstance(items, list):
        return []

    summaries = []
    for task in items:
        if not isinstance(task, dict):
            continue

        participation = task.get("participationRequirements") or {}
        if not isinstance(participation, dict):
            participation = {}

        asset = task.get("asset") or {}
        if not isinstance(asset, dict):
            asset = {}

        summaries.append({
            "id": task.get("id"),
            "slug": task.get("slug"),
            "title": task.get("title") or "Untitled task",
            "status": task.get("status"),
            "open": task.get("isOpen"),
            "deadline": task.get("deadline"),
            "tags": task.get("tags") or [],
            "requires_premium": task.get("requiresPremium"),
            "slots_remaining": task.get("standardSubmissionSlotsRemaining"),
            "minimum_twitter_followers": participation.get("minTwitterFollowers"),
            "asset_symbol": asset.get("symbol"),
            "description": plain_text(task.get("content", "")),
            "reward_note": (
                "Check the task description and submission rules. "
                "The API asset amount may represent the task pool, "
                "so it is not treated as an individual reward."
            ),
            "raw_task": task,
        })

    return summaries


def discover_tasks(limit=3, environment="stage"):
    """Request available Gibwork tasks without modifying anything."""
    if not 1 <= limit <= 100:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "INVALID_LIMIT",
                "message": "Limit must be between 1 and 100.",
            },
        }

    if environment not in ("stage", "production"):
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "INVALID_ENVIRONMENT",
                "message": "Environment must be stage or production.",
            },
        }

    if shutil.which("npx") is None:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "NPX_NOT_FOUND",
                "message": "Node.js/npm npx was not found on PATH.",
            },
        }

    command = [
        "npx", "--yes", "@gibwork/cli",
        "--profile", "stage",
    ]
    if environment == "production":
        command.extend(["--environment", "production"])

    command.extend(["--json", "task", "available", "--limit", str(limit)])

    keypair_path = os.environ.get("GIBWORK_KEYPAIR_PATH")
    if keypair_path:
        command.extend(["--keypair", keypair_path])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "TIMEOUT",
                "message": "Gibwork CLI did not respond within 45 seconds.",
            },
        }
    except OSError:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "CLI_START_FAILED",
                "message": "Could not start the Gibwork CLI.",
            },
        }

    payload = None
    for output in (completed.stdout, completed.stderr):
        if not output or not output.strip():
            continue
        try:
            payload = json.loads(output)
            break
        except (json.JSONDecodeError, TypeError):
            continue

    if payload is None:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "INVALID_RESPONSE",
                "message": (
                    "Neither CLI output stream contained valid JSON. "
                    "Check the CLI installation and try again."
                ),
            },
        }

    if isinstance(payload, dict) and payload.get("ok") is False:
        error = payload.get("error") or {}
        code = error.get("code", "GIBWORK_ERROR")
        message = error.get("message", "Gibwork returned an error.")

        if code == "CREDENTIAL_ERROR":
            message = (
                "No Gibwork wallet is configured for the selected "
                "profile. No wallet was created or changed."
            )

        return {
            "ok": False,
            "mode": "live_cli",
            "environment": environment,
            "error": {"code": code, "message": message},
        }

    if completed.returncode != 0:
        return {
            "ok": False,
            "mode": "live_cli",
            "environment": environment,
            "error": {
                "code": "CLI_FAILED",
                "message": "The Gibwork CLI returned a failure status.",
            },
        }

    return {
        "ok": True,
        "mode": "live_cli",
        "environment": environment,
        "result": payload,
        "tasks": summarize_tasks(payload),
        "notice": (
            "Read-only discovery. Review eligibility, task rules, available "
            "slots, and reward terms on Gibwork before acting."
        ),
    }


def offline_demo():
    """Return clearly labelled demonstration data; make no network calls."""
    return {
        "ok": True,
        "mode": "offline_demo",
        "notice": (
            "SAMPLE DATA ONLY. This is not a real Gibwork task "
            "and was not retrieved from Gibwork."
        ),
        "sample_task": {
            "title": "SAMPLE ONLY — Review a workflow automation task",
            "reward": "Not verified",
            "deadline": "Not verified",
            "preflight_status": "needs_review",
            "checks": {
                "requirements_clear": "unverified",
                "deadline_feasible": "unverified",
                "eligibility_confirmed": "unverified",
                "reward_verified": "unverified",
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Gibwork CLI integration for OpsPilot."
    )
    commands = parser.add_subparsers(dest="action", required=True)

    live = commands.add_parser(
        "discover",
        help="Read available tasks through the Gibwork CLI",
    )
    live.add_argument("--limit", type=int, default=3)
    live.add_argument(
        "--environment",
        choices=("stage", "production"),
        default="stage",
        help="Gibwork API environment (default: stage)",
    )

    commands.add_parser(
        "demo",
        help="Print clearly labelled offline sample data",
    )

    args = parser.parse_args()

    if args.action == "discover":
        result = discover_tasks(args.limit, args.environment)
    else:
        result = offline_demo()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
