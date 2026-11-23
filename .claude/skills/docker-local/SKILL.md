---
name: docker-local
model: claude-haiku-5-5
description: Start, inspect, tail logs of or stop a proteus agent container locally with docker compose. Use when asked to run an agent locally.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

Needs `docker-compose.override.yml` (copy `docker-compose.override.EXAMPLE.yml`) with `HARNESS`, its key and `WEBHOOK_SECRET`. Keep `DRY_RUN: "true"` unless real writes are explicitly wanted. Never print secret values.

- Start: `docker compose up -d <service>` (add `--build` after code changes; agent edits need only `docker compose restart <service>`, since agents are mounted).
- Inspect: `docker compose ps <service>`, then `curl -s localhost:<host port><prefix>/healthcheck` (port from `docker-compose.yml`).
- Logs: `docker compose logs --tail 100 <service>`. A `CRITICAL` line means misconfiguration and webhooks get `503`.
- Stop: `docker compose stop <service>` (or `down` to remove it).

Report the state, the port, and any `CRITICAL` or error lines.
