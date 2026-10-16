#!/usr/bin/env python3
"""Local-only checklist for reviewing potential Gibwork opportunities."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
STORE = DATA / "preflight.json"

DEFAULT_QUESTIONS = [
    "Are the task instructions and deliverables clear?",
    "Can I meet the stated deadline?",
    "Are eligibility requirements satisfied?",
    "Is the reward and payment condition clear?",
    "Have I checked for unusual or risky requirements?",
]


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assess(record):
    """Assess review completeness, not the truth of externally supplied claims."""
    questions = record.get("review_questions", [])
    answers = [q.get("answer", "unverified") for q in questions]
    missing_reward = record.get("reward", "Not recorded") in (
        "", "Not recorded", "Not yet verified"
    )
    missing_deadline = record.get("deadline", "Not recorded") in (
        "", "Not recorded", "Not yet verified"
    )

    if "blocked" in answers:
        status = "blocked"
    elif (
        not questions
        or any(answer != "verified" for answer in answers)
        or missing_reward
        or missing_deadline
    ):
        status = "needs_review"
    else:
        status = "ready_for_human_review"

    return {
        "status": status,
        "unanswered_checks": sum(a == "unverified" for a in answers),
        "blocked_checks": sum(a == "blocked" for a in answers),
        "missing_reward": missing_reward,
        "missing_deadline": missing_deadline,
        "note": (
            "Answers are self-assessments. Readiness does not independently "
            "verify the task, reward, deadline, eligibility, or payment."
        ),
    }


def refresh_status(record):
    record["status"] = assess(record)["status"]


def load_records():
    if not STORE.exists():
        return []
    try:
        records = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {STORE}: {exc}")
    if not isinstance(records, list):
        raise SystemExit("Preflight data must be a JSON list. No changes made.")
    return records


def save_records(records):
    DATA.mkdir(exist_ok=True)
    temp = STORE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, STORE)


def add(args):
    title = args.title.strip()
    if not title:
        raise SystemExit("Title cannot be empty.")

    records = load_records()
    record = {
        "id": max((r.get("id", 0) for r in records), default=0) + 1,
        "title": title,
        "reward": args.reward or "Not recorded",
        "deadline": args.deadline or "Not recorded",
        "requirements": args.requirement or [],
        "review_questions": [
            {"question": q, "answer": "unverified"}
            for q in DEFAULT_QUESTIONS
        ],
        "status": "needs_review",
        "created_at": timestamp(),
        "source": "manual_local_entry",
    }
    refresh_status(record)
    records.append(record)
    save_records(records)
    print(f"Saved local preflight #{record['id']}: {title}")
    print("Status: needs_review")
    print("No Gibwork request was made.")


def list_records(_args):
    records = load_records()
    if not records:
        print("No preflight records yet.")
        return
    for r in records:
        review = assess(r)
        print(f"#{r['id']} [{review['status']}] {r['title']}")
        print(f"   Reward: {r['reward']} | Deadline: {r['deadline']}")
        print(
            f"   Unanswered: {review['unanswered_checks']} "
            f"| Blocked checks: {review['blocked_checks']}"
        )
        print(
            f"   Requirements: {len(r['requirements'])} "
            f"| Unverified questions: "
            f"{sum(q['answer'] == 'unverified' for q in r['review_questions'])}"
        )


def show(args):
    records = load_records()
    for r in records:
        if r["id"] == args.id:
            print(json.dumps(r, indent=2))
            return
    raise SystemExit(f"No preflight record with ID {args.id}.")


def answer(args):
    records = load_records()
    for record in records:
        if record["id"] != args.id:
            continue

        questions = record.get("review_questions", [])
        if not 1 <= args.check <= len(questions):
            raise SystemExit(
                f"Check number must be between 1 and {len(questions)}."
            )

        questions[args.check - 1]["answer"] = args.value
        refresh_status(record)
        save_records(records)

        print(f"Updated opportunity #{record['id']}.")
        print(f"Check {args.check}: {questions[args.check - 1]['question']}")
        print(f"Answer: {args.value}")
        print(f"Assessment: {record['status']}")
        print("This assessment does not independently verify external claims.")
        return

    raise SystemExit(f"No preflight record with ID {args.id}.")


def report(_args):
    records = load_records()
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = REPORTS / f"preflight-{stamp}.json"
    md_path = REPORTS / f"preflight-{stamp}.md"

    payload = {
        "generated_at": timestamp(),
        "mode": "local-only",
        "count": len(records),
        "records": records,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Gibwork OpsPilot — Preflight Review",
        "",
        f"Generated (UTC): {payload['generated_at']}",
        "Mode: local-only; no Gibwork API calls",
        "",
    ]
    if not records:
        lines.append("No opportunities recorded.")
    for r in records:
        lines.extend([
            f"## #{r['id']} — {r['title']}",
            "",
            f"- Status: {assess(r)['status']}",
            f"- Unanswered checks: {assess(r)['unanswered_checks']}",
            f"- Blocked checks: {assess(r)['blocked_checks']}",
            f"- Assessment note: {assess(r)['note']}",
            f"- Reward: {r['reward']}",
            f"- Deadline: {r['deadline']}",
            "- Requirements:",
        ])
        if r["requirements"]:
            lines.extend(f"  - {item}" for item in r["requirements"])
        else:
            lines.append("  - Not recorded")
        lines.extend(["- Review questions:"])
        lines.extend(
            f"  - [ ] {q['question']} — {q['answer']}"
            for q in r["review_questions"]
        )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Markdown report: {md_path}")
    print(f"JSON report:     {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Local-only opportunity checklist; no wallet required."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("add", help="Record an opportunity for review")
    p.add_argument("title")
    p.add_argument("--reward", help="Reward exactly as advertised")
    p.add_argument("--deadline", help="Deadline exactly as advertised")
    p.add_argument(
        "--requirement", action="append",
        help="Requirement; repeat this option for multiple items",
    )
    p.set_defaults(func=add)

    p = commands.add_parser("list", help="List recorded opportunities")
    p.set_defaults(func=list_records)

    p = commands.add_parser("show", help="Show a record by local ID")
    p.add_argument("id", type=int)
    p.set_defaults(func=show)

    p = commands.add_parser("answer", help="Record an answer to a review check")
    p.add_argument("id", type=int, help="Local opportunity ID")
    p.add_argument("--check", type=int, required=True, help="Check number from 1")
    p.add_argument(
        "--value",
        choices=("verified", "blocked", "unverified"),
        required=True,
    )
    p.set_defaults(func=answer)

    p = commands.add_parser("report", help="Generate Markdown and JSON reports")
    p.set_defaults(func=report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
