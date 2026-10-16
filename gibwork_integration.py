#!/usr/bin/env python3
"""Safe, read-only integration with the Gibwork CLI."""

import argparse
import json
import shutil
import subprocess


def discover_tasks(limit=3):
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
        "npx", "--yes", "@gibwork/cli", "--json",
        "task", "available", "--limit", str(limit),
    ]

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
                "No Gibwork wallet is configured. Live discovery is "
                "unavailable; no wallet was created or changed."
            )

        return {
            "ok": False,
            "mode": "live_cli",
            "error": {"code": code, "message": message},
        }

    if completed.returncode != 0:
        return {
            "ok": False,
            "mode": "live_cli",
            "error": {
                "code": "CLI_FAILED",
                "message": "The Gibwork CLI returned a failure status.",
            },
        }

    return {
        "ok": True,
        "mode": "live_cli",
        "result": payload,
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

    commands.add_parser(
        "demo",
        help="Print clearly labelled offline sample data",
    )

    args = parser.parse_args()

    if args.action == "discover":
        result = discover_tasks(args.limit)
    else:
        result = offline_demo()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
