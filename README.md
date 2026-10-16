# Gibwork OpsPilot

**A local-first opportunity review and developer operations assistant.**

Gibwork OpsPilot helps developers record work opportunities, assess readiness before committing, track tasks, and export portable Markdown and JSON reports. Its Gibwork CLI adapter attempts read-only task discovery and reports credential or CLI errors without pretending that live access succeeded.

## Current status

- Local task tracking and report generation.
- Opportunity preflight checklist with review answers and readiness assessment.
- Read-only Gibwork CLI task-discovery adapter.
- Automated tests for task tracking, assessment rules, and CLI response handling.
- Offline demonstration mode with explicitly labelled sample data.

**Live integration status:** task discovery requires working Gibwork CLI credentials. Without them, OpsPilot reports the error. Mocked tests do not prove live Gibwork access.

## Requirements

- Python 3.9 or newer.
- Node.js/npm with `npx` for Gibwork CLI discovery.
- The Gibwork CLI package is invoked through `npx`.

Local task tracking, preflight reviews, offline demo, and automated tests do not require a wallet.

## Quick start

Run commands from the project directory.

### 1. Check local tasks

```sh
python opspilot.py status
python opspilot.py list
```

Add a task and export a report:

```sh
python opspilot.py add "Review an automation opportunity" \
  --notes "Read requirements and confirm eligibility"
python opspilot.py report
```

### 2. Record an opportunity

```sh
python preflight.py add "Example opportunity — replace with a real listing" \
  --reward "Not yet verified" \
  --deadline "Not yet verified" \
  --requirement "Read the complete task description" \
  --requirement "Confirm eligibility and deliverables"
```

List records and inspect a record by its local ID:

```sh
python preflight.py list
python preflight.py show 1
```

Answer a review check:

```sh
python preflight.py answer 1 --check 1 --value verified
```

Allowed values are `verified`, `blocked`, and `unverified`. These are user-entered review judgments, not independent proof that a listing or claim is genuine.

Generate Markdown and JSON reports:

```sh
python preflight.py report
```

### 3. Try the offline demo

```sh
python gibwork_integration.py demo
```

This displays sample data clearly labelled as a demonstration. It does not fetch a real task or make a network request.

### 4. Attempt live Gibwork discovery

```sh
python gibwork_integration.py discover --limit 3
```

The limit must be between 1 and 100. The command uses the Gibwork CLI's read-only available-task operation. It can fail if credentials are not configured, the CLI is unavailable, or the service cannot be reached. A failure is reported rather than converted into fabricated task results.

Do not share wallet private keys or recovery phrases. This project does not create or fund a wallet.

## Readiness assessment

Each opportunity has review questions covering:

- Clarity of instructions and deliverables.
- Deadline feasibility.
- Eligibility.
- Reward and payment conditions.
- Unusual or risky requirements.

An opportunity can be marked `blocked`, `needs_review`, or `ready_for_human_review`. The last status means the checklist is complete according to the recorded answers and reward/deadline fields. It does not mean the software independently verified the task, payment, eligibility, or deadline.

## Data and reports

- Local task records: `data/tasks.json`
- Local opportunity records: `data/preflight.json`
- Generated Markdown and JSON reports: `reports/`

Keep personal data and credentials out of reports and public commits. Review generated files before publishing.

## Run automated tests

```sh
python -m py_compile opspilot.py preflight.py gibwork_integration.py
python -m unittest discover -s tests -v
```

The integration tests mock CLI responses. They verify wrapper behaviour without a wallet or network, not successful live access to Gibwork.

## Safety and limitations

- Local task and preflight records are not submitted to Gibwork.
- The current integration is read-only and does not create, edit, submit, or refund tasks.
- Sample data is never presented as live discovery.
- Readiness is a checklist-based aid for human decisions, not a guarantee of reward, payment, or eligibility.
- Do not commit secrets, wallet files, tokens, or private account data.

## Project goal

Provide a practical, auditable workflow for reviewing opportunities before committing time or resources, with clear status reporting and portable artifacts.
