---
name: lint
model: claude-haiku-5-5
description: Run ruff (lint and format check) and mypy on the proteus code. Use when asked to lint, type-check or check code style.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy runner tests` from the repo root.
2. If a tool is not found, run the `refresh-dependencies` skill steps and retry once.
3. Report pass/fail per tool, with each finding as `file:line` and message. Do not fix anything unless asked.
