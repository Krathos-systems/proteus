---
name: check-agent
model: claude-sonnet-5-5
description: Validate a proteus agent directory without Docker or credentials: run the runner's own loader, then review it for loose patterns, misfiled write tools and re-trigger loops. Use after creating or editing an agent, or when an agent logs CRITICAL / answers 503.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: sonnet`) with the full instructions below, and relay its findings. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

Changes nothing; report findings and let the user decide.

## 1. Run the real loader
Use the runner's own validation, so the result matches what the container will log. Give every `requiredEnv` name a dummy value (it only checks presence):

```bash
AGENTS_DIR=agents AGENT=<name> HARNESS=claude WEBHOOK_SECRET=x <REQUIRED_ENV>=dummy … \
  uv run python -c "from runner.config import config_errors, agent; print(config_errors or 'ok'); print(agent.path_prefix, dict(agent.tools))"
```

Use `AGENTS_DIR=examples` for the examples. Anything other than `ok` is what the container's `CRITICAL` line would say. Repeat with `DRY_RUN=true` and confirm the write tools disappear from the printed tools.

## 2. Review what the loader cannot
- **Input patterns:** each one is tight (an ID, a key, a short title), not `.*` or open free text. Values are pasted into the prompt, so a loose pattern lets a webhook sender inject instructions.
- **Tools:** every `tools` entry really only reads; anything that creates, edits, posts or transitions is in `writeTools`. Use `find-mcp-tools` if unsure.
- **mcp.json:** secrets only as `${VAR}`, every `${VAR}` listed in `requiredEnv`, no server left without tools (it is never started).
- **Skill:** front matter `name` equals `skill` in `agent.json`; it says what the output is, where it goes, its length, and what the agent must never do; tool names in it match `tools`/`writeTools`.
- **Loops:** the agent's write cannot fire the trigger that started it.
- **Compose:** a service exists in `docker-compose.yml` with `AGENT: <name>`, a unique `127.0.0.1` host port, and the default read-only `./agents` mount. `uv run pytest tests/repo` checks the ports and mount.

Report each finding as file, problem, suggested fix, or "agent looks good".
