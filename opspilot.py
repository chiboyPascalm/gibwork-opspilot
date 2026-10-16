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


def cmd_report(_args):
    tasks = load_tasks()
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "generated_at": now(),
        "project": ROOT.name,
        "mode": "local-only",
        "total_tasks": len(tasks),
        "open_tasks": sum(t.get("status") == "open" for t in tasks),
        "tasks": tasks,
    }
    json_path = REPORTS / f"report-{stamp}.json"
    md_path = REPORTS / f"report-{stamp}.md"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Gibwork OpsPilot — Local Task Report",
        "",
        f"- Generated (UTC): {summary['generated_at']}",
        "- Mode: local-only; no Gibwork API calls",
        f"- Total tasks: {summary['total_tasks']}",
        f"- Open tasks: {summary['open_tasks']}",
        "",
        "## Tasks",
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
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Markdown report: {md_path}")
    print(f"JSON report:     {json_path}")


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
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
