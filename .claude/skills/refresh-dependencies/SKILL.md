---
name: refresh-dependencies
model: claude-haiku-5-5
description: Reinstall the proteus dev dependencies from uv.lock and confirm with lint. Use when .venv is missing or stale, or lint/tests fail because a tool is not found.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. Run `uv sync` from the repo root (installs the dev group from `uv.lock`; Python version from `.python-version`).
2. Run the `lint` skill steps to confirm the tools work.
3. Report what `uv sync` changed and the lint result.
