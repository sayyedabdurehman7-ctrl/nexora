---
title: NEXORA
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# NEXORA

An Autonomous Multimodal Personal AI Agent for Goal-Based Task Planning, Tool Selection,
and Cross-Application Execution — a Computer Science Final Year Project.

The research contribution is an explainable planner/executor/verifier/recovery loop.
This first slice is deliberately deterministic: a mock planner turns supported commands
into ordered steps, tools return evidence, and a separate verifier checks each result.

## Run

See [Windows setup](docs/SETUP.md) for exact commands. After installation, run
`nexora-api` in one terminal and `nexora-ui` in another from this project folder.
No API key or internet is used by the running backend or tests. Flet's desktop runtime
may need downloading once during installation/first launch.

## Try these goals

- `calculate 2 + 3 * 4`
- `list files`
- `read notes.txt` (put your own UTF-8 text file in `data/user_files` first)
- `search hello in notes.txt`
- `calculate 5 * 8 then list files`
- `approval demo` (only acknowledges a simulated action in this task's SQLite record)

Click Create plan, inspect its inputs and steps, then Run task. Approval demo shows an
exact preview with Approve/Reject. Stop cancels the selected run. History survives restart.
Commands are English and use the literal separator ` then `; general questions and
arbitrary natural-language goals are unsupported. Never paste secrets into goals or files.

## Architecture and safety

Flet -> local FastAPI -> plain Python core -> provider protocol / registry / policy -> SQLite.
Only calculator and read-only file tools are registered in Phase 1. File operations are
limited to an approved directory, supported text types, 256 KiB and 500 entries per folder.
Calculator uses a bounded AST interpreter. No shell execution, external writes or deletion.
Audit events contain fixed messages, while task history intentionally retains goals and
evidence locally. Keep private or secret content out of the approved workspace.

Runs have deadlines, bounded retries for transient I/O, and cooperative cancellation.
Verification mismatches fail closed. Exact approval is bound to the task and plan and
consumed once. Interrupted runs are marked failed on service restart.

## Tests

`python -m pytest` and `python -m ruff check .` plus `python -m ruff format --check .`.
Tests use temporary data, injected failures and no cloud services.

## Limitations and roadmap

This is a single-user local prototype. Run one backend process only. It has no authentication,
so do not expose it to a network. File reads are bounded but synchronous local I/O; a stalled
filesystem cannot be forcibly interrupted by asyncio. Avoid network shares. Workspace access
assumes no hostile process swaps filesystem entries during a read; stronger OS isolation is
future hardening. SQLite stores versioned task/plan/approval snapshots plus separate audit rows;
normalize additional tables and introduce migrations when schema evolution begins.

Phase 2 completes the five-tool MVP with PDF, search, memory management and optional AI.
Phase 3 adds research/browser capability; Phase 4 voice/screen features; Phase 5 evaluates
50–100 repeatable tasks against a baseline. No evaluation results exist yet.
See [specification](docs/PROJECT_SPEC.md) and [verified progress](docs/PROGRESS.md).
