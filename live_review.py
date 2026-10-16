#!/usr/bin/env python3
"""Read-only review of live Gibwork listings with optional report export."""

import argparse
import json
import re
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path

from gibwork_integration import discover_tasks



def analyze_reward(description):
    """Extract only explicitly described per-person or performance rewards."""
    if not isinstance(description, str):
        description = ""

    found = []

    # Explicit base/fixed amounts, e.g. "$25 base reward"
    # or "The base reward is $25".
    for match in re.finditer(
        r'(?i)(?:'
        r'([$€£]\s?\d[\d,]*(?:\.\d{1,2})?)\s+'
        r'(?:is\s+)?(?:the\s+)?(?:base|fixed)(?:\s+reward| payment)?'
        r'|(?:base|fixed)(?:\s+reward| payment)?\s+'
        r'(?:is\s+)?([$€£]\s?\d[\d,]*(?:\.\d{1,2})?)'
        r')',
        description,
    ):
        amount = match.group(1) or match.group(2)
        item = amount.replace(" ", "") + " base reward"
        if item not in found:
            found.append(item)

    # Explicit per-submission amounts, e.g. "1 USDC each".
    for match in re.finditer(
        r'(?i)([$€£]\s?\d[\d,]*(?:\.\d{1,2})?'
        r'|\d[\d,]*(?:\.\d{1,2})?\s*(?:USDC|USDT|USD|SOL))'
        r'\s*(?:USDC|USDT|USD|SOL)?\s*'
        r'(?:each|per\s+(?:approved\s+)?submission|'
        r'per\s+approved\s+entry)',
        description,
    ):
        amount = re.sub(r'\s+', '', match.group(1))
        item = amount + " per submission (advertised)"
        if item not in found:
            found.append(item)

    # Performance-based amounts, e.g. "$1.50 per 1,000 video views".
    for match in re.finditer(
        r'(?i)([$€£]\s?\d[\d,]*(?:\.\d{1,2})?)\s*'
        r'per\s+([\d,]+)\s+([a-z][a-z ]{0,30})'
        r'(?=[,.;!?)]|$)',
        description,
    ):
        item = (
            re.sub(r'\s+', '', match.group(1))
            + " per "
            + match.group(2)
            + " "
            + match.group(3).strip()
            + " (performance-based; verify terms)"
        )
        # Treat "video views" and "views" as equivalent
        # when the advertised rate and amount are identical.
        normalized_item = re.sub(
            r'\bvideo\s+(?=views\b)', '', item, flags=re.I
        )
        already_recorded = any(
            re.sub(r'\bvideo\s+(?=views\b)', '', existing, flags=re.I)
            == normalized_item
            for existing in found
            if "(performance-based" in existing
        )
        if not already_recorded:
            found.append(item)

    return {
        "advertised_reward": "; ".join(found) if found else
            "Individual reward not established from description",
        "reward_confidence": "description_match_needs_verification"
            if found else "unknown",
        "reward_warning": (
            "Extracted from description only; verify eligibility, "
            "approval conditions, and payment terms. Not a guarantee."
        ),
    }


def priority_details(task, blockers):
    """Transparent review triage, not a prediction of eligibility or earnings."""
    if blockers:
        return {
            "priority_score": 0,
            "priority": "blocked",
            "priority_reasons": ["A listing-level blocker was identified."],
        }

    score = 100
    reasons = ["No listing-level blocker identified."]

    if task.get("slots_remaining") is None:
        score -= 15
        reasons.append("Slot availability is unknown.")
    if task.get("requires_premium") is True:
        score -= 10
        reasons.append("Premium access needs confirmation.")

    followers = task.get("minimum_twitter_followers")
    if isinstance(followers, int) and followers > 0:
        score -= 10
        reasons.append(
            f"Linked X account must meet the {followers}-follower minimum."
        )

    if not task.get("deadline"):
        score -= 5
        reasons.append("Deadline needs confirmation.")

    score = max(0, score)
    priority = "high" if score >= 80 else "medium" if score >= 60 else "low"

    return {
        "priority_score": score,
        "priority": priority,
        "priority_reasons": reasons,
    }


def duplicate_similarity(first, second):
    """Return title similarity; this is a warning signal, not proof."""
    a = re.sub(r"[^a-z0-9]+", " ", (first or "").lower()).strip()
    b = re.sub(r"[^a-z0-9]+", " ", (second or "").lower()).strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


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

    result = {
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
        **analyze_reward(task.get("description", "")),
    }
    result.update(priority_details(task, blockers))
    return result


def build_report(tasks, environment):
    reviewed = [review_task(task) for task in tasks]

    # Flag likely duplicates; keep every listing visible for human review.
    for item in reviewed:
        item["possible_duplicates"] = []

    for index, first in enumerate(reviewed):
        for second in reviewed[index + 1:]:
            first_id, second_id = first.get("id"), second.get("id")
            if first_id and second_id and first_id == second_id:
                continue
            similarity = duplicate_similarity(
                first.get("title"), second.get("title")
            )
            if similarity >= 0.88:
                first["possible_duplicates"].append({
                    "id": second_id,
                    "title": second.get("title"),
                    "title_similarity": round(similarity, 2),
                })
                second["possible_duplicates"].append({
                    "id": first_id,
                    "title": first.get("title"),
                    "title_similarity": round(similarity, 2),
                })

    reviewed.sort(
        key=lambda item: item.get("priority_score", 0),
        reverse=True,
    )
    for rank, item in enumerate(reviewed, start=1):
        item["review_rank"] = rank

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
            f"- **Review rank:** {task.get('review_rank', 'Not ranked')}",
            f"- **Priority:** {task.get('priority', 'unknown')} "
            f"(score {task.get('priority_score', 'unknown')}/100; triage only)",
            f"- **Advertised reward:** {task.get('advertised_reward', 'Unknown')}",
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
        if task.get("reward_warning"):
            lines.append("")
            lines.append(f"**Reward verification:** {task['reward_warning']}")
        if task.get("possible_duplicates"):
            lines.extend(["", "**Possible duplicate listings**", ""])
            for duplicate in task["possible_duplicates"]:
                lines.append(
                    f"- {duplicate.get('title') or 'Untitled'} "
                    f"(ID: {duplicate.get('id') or 'unknown'}, "
                    f"title similarity: {duplicate['title_similarity']})"
                )
            lines.append(
                "- Similar titles are only a warning; inspect the listings "
                "before deciding whether they are duplicates."
            )
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
