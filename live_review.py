#!/usr/bin/env python3
"""Read-only review of live Gibwork listings with optional report export."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from gibwork_integration import discover_tasks


def review_task(task):
    blockers = []
    checks = []

    if task.get("open") is False:
        blockers.append("Listing is not open.")

    slots = task.get("slots_remaining")
    if isinstance(slots, int) and slots <= 0:
        blockers.append("No standard submission slots remain.")
    elif slots is None:
        checks.append("Confirm available submission slots on Gibwork.")

    if task.get("requires_premium") is True:
        checks.append("Premium access is required; confirm you have it.")

    followers = task.get("minimum_twitter_followers")
    if isinstance(followers, int) and followers > 0:
        checks.append(
            f"Confirm your linked X account meets the "
            f"{followers}-follower minimum."
        )

    deadline = task.get("deadline")
    if deadline:
        try:
            due = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due <= datetime.now(timezone.utc):
                blockers.append("Listed deadline has passed.")
            else:
                checks.append(f"Deadline listed as {deadline}.")
        except (ValueError, TypeError, AttributeError):
            checks.append("Check the deadline directly on Gibwork.")
    else:
        checks.append("No deadline listed; confirm the task terms.")

    checks.append(
        "Read the full task rules and verify reward, eligibility, "
        "deliverables, and payment terms before acting."
    )

    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": "blocked_by_listing" if blockers else "needs_human_review",
        "blockers": blockers,
        "checks": checks,
        "deadline": deadline,
        "slots_remaining": slots,
        "requires_premium": task.get("requires_premium"),
        "minimum_twitter_followers": followers,
        "reward_note": task.get("reward_note"),
        "description": task.get("description"),
    }


def build_report(tasks, environment):
    reviewed = [review_task(task) for task in tasks]
    return {
        "mode": "read_only",
        "environment": environment,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(reviewed),
        "notice": (
            "No tasks or preflight records were saved or changed. "
            "A review is not a guarantee of eligibility or payment."
        ),
        "tasks": reviewed,
    }


def render_markdown(report):
    lines = [
        "# Gibwork OpsPilot Opportunity Review",
        "",
        f"- **Environment:** {report['environment']}",
        f"- **Generated:** {report['generated_at']}",
        f"- **Listings reviewed:** {report['count']}",
        "- **Mode:** Read-only",
        "",
        "> This report does not guarantee eligibility, approval, or payment.",
        "",
        "## Results",
        "",
    ]

    if not report["tasks"]:
        lines.append("No listings were returned.")
        lines.append("")

    for index, task in enumerate(report["tasks"], start=1):
        lines.extend([
            f"### {index}. {task.get('title') or 'Untitled listing'}",
            "",
            f"- **Status:** `{task['status']}`",
            f"- **Listing ID:** `{task.get('id') or 'Not provided'}`",
            f"- **Deadline:** {task.get('deadline') or 'Not listed'}",
            f"- **Slots remaining:** {task.get('slots_remaining') if task.get('slots_remaining') is not None else 'Unknown'}",
            f"- **Premium required:** {task.get('requires_premium') if task.get('requires_premium') is not None else 'Unknown'}",
            f"- **Minimum X followers:** {task.get('minimum_twitter_followers') if task.get('minimum_twitter_followers') is not None else 'Unknown'}",
            "",
            "**Blockers**",
            "",
        ])
        if task["blockers"]:
            lines.extend(f"- {item}" for item in task["blockers"])
        else:
            lines.append("- No listing-level blocker identified.")
        lines.extend(["", "**Manual checks**", ""])
        if task["checks"]:
            lines.extend(f"- {item}" for item in task["checks"])
        else:
            lines.append("- None recorded.")
        if task.get("reward_note"):
            lines.extend(["", f"**Reward note:** {task['reward_note']}"])
        lines.append("")

    lines.extend([
        "## Limitations",
        "",
        "This automated review only evaluates fields returned by the CLI. "
        "It cannot confirm your account eligibility, current slot availability "
        "when that field is missing, task approval, or payment. Verify the "
        "full listing on Gibwork before acting.",
        "",
    ])
    return "\n".join(lines)


def save_report(report):
    output_dir = Path("reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"live-review-{stamp}.json"
    markdown_path = output_dir / f"live-review-{stamp}.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main():
    parser = argparse.ArgumentParser(
        description="Review live Gibwork listings without submitting."
    )
    parser.add_argument(
        "--environment",
        choices=("stage", "production"),
        default="production",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save timestamped JSON and Markdown reports in reports/",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    result = discover_tasks(args.limit, args.environment)
    if not result.get("ok"):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    report = build_report(result.get("tasks", []), args.environment)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.save:
        json_path, markdown_path = save_report(report)
        print("\nReports saved:")
        print(f"JSON: {json_path}")
        print(f"Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
