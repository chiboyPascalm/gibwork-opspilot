#!/usr/bin/env python3
"""Local-first task tracker for Gibwork OpsPilot. Uses Python stdlib only."""

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
TASKS = DATA / "tasks.json"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_tasks():
    if not TASKS.exists():
        return []
    try:
        data = json.loads(TASKS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot safely read {TASKS}: {exc}")
    if not isinstance(data, list):
        raise SystemExit("tasks.json must contain a JSON list; no changes made.")
    return data


def save_tasks(tasks):
    DATA.mkdir(exist_ok=True)
    temp = TASKS.with_suffix(".json.tmp")
    temp.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, TASKS)


def cmd_status(_args):
    print("Gibwork OpsPilot — local status")
    print(f"Python:   {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"Project:  {ROOT}")
    print(f"Tasks:    {TASKS}")
    print(f"Reports:  {REPORTS}")
    print("Mode:     local-only; no network requests")
    print(f"Records:  {len(load_tasks())}")


def cmd_add(args):
    title = args.title.strip()
    if not title:
        raise SystemExit("Task title cannot be empty.")
    tasks = load_tasks()
    task = {
        "id": max((t.get("id", 0) for t in tasks), default=0) + 1,
        "title": title,
        "notes": args.notes or "",
        "status": "open",
        "created_at": now(),
        "source": "local",
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"Added local task #{task['id']}: {task['title']}")


def cmd_list(_args):
    tasks = load_tasks()
    if not tasks:
        print("No local tasks yet.")
        return
    for task in tasks:
        print(f"#{task['id']} [{task['status']}] {task['title']}")
        if task.get("notes"):
            print(f"   {task['notes']}")


def cmd_sync(args):
    """Import real Gibwork task listings into local storage."""
    try:
        from gibwork_integration import discover_tasks
    except ImportError as exc:
        raise SystemExit(
            f"Cannot load Gibwork integration: {exc}"
        )

    result = discover_tasks(
        limit=args.limit,
        environment=args.environment,
    )

    if not result.get("ok"):
        error = result.get("error") or {}
        raise SystemExit(
            "Gibwork discovery failed: "
            + str(error.get("code", "UNKNOWN_ERROR"))
            + " — "
            + str(error.get("message", "No details supplied."))
        )

    summaries = result.get("tasks", [])
    if not isinstance(summaries, list):
        raise SystemExit("Invalid task summary; no changes made.")

    tasks = load_tasks()
    existing = {
        str(task.get("external_id"))
        for task in tasks
        if task.get("source") == "gibwork"
        and task.get("external_id") is not None
    }
    numeric_ids = [
        task.get("id")
        for task in tasks
        if type(task.get("id")) is int
    ]
    next_id = max(numeric_ids, default=0) + 1
    imported = 0
    skipped = 0

    for item in summaries:
        if not isinstance(item, dict):
            skipped += 1
            continue

        external_id = item.get("id")
        if external_id is None or not str(external_id).strip():
            skipped += 1
            continue

        external_id = str(external_id)
        if external_id in existing:
            skipped += 1
            continue

        is_open = item.get("open")
        local_status = (
            "open" if is_open is True
            else "closed" if is_open is False
            else "unknown"
        )

        description = item.get("description") or ""
        reward_note = item.get("reward_note") or ""

        tasks.append({
            "id": next_id,
            "source": "gibwork",
            "external_id": external_id,
            "slug": item.get("slug"),
            "title": item.get("title") or "Untitled Gibwork task",
            "notes": description,
            "reward_note": reward_note,
            "asset_symbol": item.get("asset_symbol"),
            "tags": item.get("tags") or [],
            "deadline": item.get("deadline"),
            "status": local_status,
            "gibwork_status": item.get("status"),
            "requires_premium": item.get("requires_premium"),
            "slots_remaining": item.get("slots_remaining"),
            "minimum_twitter_followers": item.get(
                "minimum_twitter_followers"
            ),
            "environment": args.environment,
            "created_at": now(),
        })

        existing.add(external_id)
        next_id += 1
        imported += 1

    if imported:
        save_tasks(tasks)

    print("Gibwork task sync complete")
    print(f"Environment: {args.environment}")
    print(f"Imported:    {imported}")
    print(f"Skipped:     {skipped} (duplicates or invalid records)")
    print("No tasks were accepted, submitted, funded, or refunded.")


def cmd_report(_args):
    """Generate local task reports with read-only opportunity reviews."""
    tasks = load_tasks()
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Only review listings previously imported from Gibwork.
    # Local notes are not treated as live opportunity listings.
    review_inputs = []
    for task in tasks:
        if task.get("source") != "gibwork":
            continue

        local_status = task.get("status")
        is_open = (
            True if local_status == "open"
            else False if local_status == "closed"
            else None
        )

        review_inputs.append({
            "id": task.get("external_id") or task.get("id"),
            "title": task.get("title"),
            "open": is_open,
            "deadline": task.get("deadline"),
            "slots_remaining": task.get("slots_remaining"),
            "requires_premium": task.get("requires_premium"),
            "minimum_twitter_followers": task.get(
                "minimum_twitter_followers"
            ),
            "description": task.get("notes") or "",
            "reward_note": task.get("reward_note"),
        })

    environments = [
        task.get("environment")
        for task in tasks
        if task.get("source") == "gibwork" and task.get("environment")
    ]
    environment = environments[0] if environments else "stage"

    if review_inputs:
        try:
            from live_review import build_report, render_markdown
        except ImportError as exc:
            raise SystemExit(
                "Cannot review saved Gibwork listings because "
                f"live_review.py is unavailable: {exc}"
            )

        opportunity_review = build_report(review_inputs, environment)
        review_markdown = render_markdown(opportunity_review)
    else:
        # Keep local-only reports independent of the optional review module.
        opportunity_review = {
            "mode": "read_only",
            "environment": environment,
            "generated_at": now(),
            "count": 0,
            "notice": "No saved Gibwork listings are available to review.",
            "tasks": [],
        }
        review_markdown = (
            "## Opportunity Review\n\n"
            "No saved Gibwork listings are available to review."
        )

    summary = {
        "generated_at": now(),
        "project": ROOT.name,
        "mode": "local-only",
        "total_tasks": len(tasks),
        "open_tasks": sum(t.get("status") == "open" for t in tasks),
        "tasks": tasks,
        "opportunity_review": opportunity_review,
    }

    json_path = REPORTS / f"report-{stamp}.json"
    md_path = REPORTS / f"report-{stamp}.md"

    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Gibwork OpsPilot — Local Task Report",
        "",
        f"- Generated (UTC): {summary['generated_at']}",
        "- Mode: local-only; no Gibwork API calls",
        f"- Total tasks: {summary['total_tasks']}",
        f"- Open tasks: {summary['open_tasks']}",
        "",
        "## Saved Tasks",
        "",
    ]

    if tasks:
        for task in tasks:
            lines.append(
                f"- **#{task['id']} — {task['title']}** "
                f"({task.get('status', 'unknown')})"
            )
            if task.get("notes"):
                lines.append(f"  - Notes: {task['notes']}")
    else:
        lines.append("No local tasks recorded.")

    lines.extend([
        "",
        "---",
        "",
        review_markdown,
    ])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Markdown report: {md_path}")
    print(f"JSON report:     {json_path}")
    print(
        "Gibwork opportunities reviewed: "
        f"{opportunity_review['count']}"
    )
    print("Read-only review; no tasks were accepted or submitted.")


def main():
    parser = argparse.ArgumentParser(
        description="Local-first Gibwork OpsPilot; no wallet required."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("status", help="Inspect local project status")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("add", help="Add a local task (does not submit to Gibwork)")
    p.add_argument("title", help="Task title")
    p.add_argument("--notes", default="", help="Optional notes")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("list", help="List local tasks")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("report", help="Generate Markdown and JSON reports")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser(
        "sync",
        help="Import available Gibwork tasks into local storage",
    )
    p.add_argument(
        "--limit", type=int, choices=range(1, 101),
        default=5, help="Maximum tasks to discover (1-100)",
    )
    p.add_argument(
        "--environment", choices=("stage", "production"),
        default="stage", help="Gibwork environment (default: stage)",
    )
    p.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
