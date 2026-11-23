---
name: docs-sync
model: claude-sonnet-5-5
description: Review the current changes (branch diff and working tree) and check whether README.md, CLAUDE.md or any skill in .claude/skills needs updating. Use before opening a PR or when asked to check that documentation is still accurate.
---

**Execution:** delegate steps 1–3 to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: sonnet`) with the instructions below, and relay its report. Step 4 (applying edits) happens only in the main session after the user approves. If you are already running as a sub-agent, do not delegate again: do steps 1–3 directly.

1. Collect the changes: `git diff main...HEAD`, `git diff` and `git status`.
2. For each change in behaviour, commands, env vars, harnesses, agent format or repo layout, check `README.md`, `CLAUDE.md` and every `.claude/skills/*/SKILL.md` for text it makes wrong or incomplete.
3. Report each stale passage as file, line, what is wrong and the proposed wording.
4. Edit only after the user approves.
