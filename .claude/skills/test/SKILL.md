---
name: test
model: claude-haiku-5-5
description: Run the proteus automated tests (pytest, in parallel) for all areas or one. Use when asked to run or check tests, or to reproduce the CI test job.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. All areas: `uv run pytest`. One area: `uv run pytest tests/<area>` (`http`, `invocation`, `agents`, `repo`). One test: `uv run pytest -n0 <file> -k <text>`.
2. If pytest is not found, run the `refresh-dependencies` skill steps and retry once.
3. Report passed/failed/skipped counts and, for each failure, the test id and the assertion or error line. Do not edit tests to make them pass; if behaviour changed on purpose, say so.
