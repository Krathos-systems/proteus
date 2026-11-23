---
name: test-webhook
model: claude-haiku-5-5
description: Send a test webhook to a locally running proteus agent and report the response and what the agent logged. Use when asked to trigger or try an agent end to end locally.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. Make sure the agent is running (`docker-local` skill steps). Read its `agent.json` for `pathPrefix` (default `/<agent>`) and the `input` fields and patterns, and the host port from `docker-compose.yml`.
2. Send a body whose values fully match each `pattern`, using the secret from `docker-compose.override.yml` without echoing it:
   `curl -s -w '\n%{http_code}\n' -X POST localhost:<port><prefix>/webhook -H "X-Webhook-Secret: $SECRET" -H 'Content-Type: application/json' -d '{"<field>":"<value>"}'`
3. Expect `202` (`401` bad secret, `400` bad field, `503` not configured). Then follow `docker compose logs -f <service>` until the job finishes or times out.
4. Report the status code and the job's start, result (the dry-run report if `DRY_RUN`) and any errors.
