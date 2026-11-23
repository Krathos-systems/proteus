---
name: review
model: claude-sonnet-5-5
description: Run the full pre-review check for proteus (install, lint, type-check, tests, build and smoke-test every agent image). Use before opening a PR.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: sonnet`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

Stop at the first failing step and report it.
1. `refresh-dependencies` skill steps (`uv sync`).
2. `lint` skill steps (ruff check, ruff format --check, mypy --strict).
3. `test` skill steps (all areas).
4. If Docker is available: `docker-build`, then `smoke-test` skill steps. Otherwise say they were skipped.
5. Report each step as passed, failed (with the key error) or skipped.
