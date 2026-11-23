---
name: add-agent
model: claude-sonnet-5-5
description: Turn an idea into a new proteus agent (agents/<name>, mcp.json, skill, compose service), from design through a dry-run test. Use when asked to add, create or set up a new agent or webhook automation.
---

**Execution:** do step 1 (design) in the main session, because it needs answers from the user. Then delegate steps 2–3 to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: sonnet`), passing the agreed spec and these instructions, and relay its concise result. If you are already running as a sub-agent, do not delegate again: do steps 2–3 directly.

Never commit or push, and never put secret values in files (only `${VAR}` placeholders).

## 1. Design first
Before creating files, get answers to the five questions in README "From idea to agent", step 1. Ask the user for anything they have not said:

| Question | Becomes |
|---|---|
| Which event starts it, and which fields does it send? | `input` (one tight full-match `pattern` per field) |
| What should it do, step by step? | the skill's `SKILL.md` |
| What does it need to read? | `tools` + `mcp.json` |
| What may it change? | `writeTools` (empty is a fine start) |
| Where does the result go? | the skill + `writeTools` |

Push back on free-text inputs (values land in the prompt) and on an "and then" in the job (suggest two agents). Make sure the agent's own write cannot re-trigger the event that started it. Show the user the resulting spec before you build it.

## 2. Build
Follow README "From idea to agent" from step 2 on (`runner new`, `agent.json`, `mcp.json`, the skill, the compose service). For exact tool names, use the `find-mcp-tools` skill rather than guessing them.

## 3. Verify
- Run the `check-agent` skill on the new agent and fix what it reports.
- If the user has Docker and credentials: `docker-local` with `DRY_RUN: "true"`, then `test-webhook`.
- Report the files created, the compose port, the env vars the user still has to set, and open questions.
