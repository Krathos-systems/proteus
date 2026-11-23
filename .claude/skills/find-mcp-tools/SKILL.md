---
name: find-mcp-tools
model: claude-sonnet-5-5
description: List the exact tool names an MCP server exposes and sort them into read-only (tools) and changing (writeTools) for a proteus agent. Use when writing or checking an agent's tools/writeTools, or when a tool name is unknown.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: sonnet`) with the full instructions below, and relay its table. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

`tools`/`writeTools` entries must be exact `server/tool` names, where `server` is the key in the agent's `mcp.json`. Never guess a name: an unknown tool is silently unavailable to the agent.

## Get the list
Credentials come from the user's environment or override file. Never print, log or write them anywhere; pass them as shell variables.

**HTTP server** (`url` in `mcp.json`), with plain curl (streamable HTTP; responses may come back as SSE `data:` lines):

```bash
URL=https://mcp.example.com/mcp; AUTH="Authorization: Basic $JIRA_AUTH"
H=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -H "$AUTH")
SID=$(curl -s -D - -o /dev/null "${H[@]}" "$URL" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"tool-lister","version":"0"}}}' | grep -i '^mcp-session-id' | cut -d' ' -f2 | tr -d '\r')
curl -s "${H[@]}" ${SID:+-H "Mcp-Session-Id: $SID"} "$URL" -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
curl -s "${H[@]}" ${SID:+-H "Mcp-Session-Id: $SID"} "$URL" -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | sed 's/^data: //' | grep '^{' | python3 -m json.tool
```

**stdio server** (`command` in `mcp.json`): `npx @modelcontextprotocol/inspector --cli <command> <args…> --method tools/list` (check `--help` if flags differ). Or read the server's docs or source.

If you cannot reach the server (no credentials, no network), use its documentation and say so in the report.

## Classify
For each tool, decide read vs write from its description and `annotations` (`readOnlyHint: true` → read; `destructiveHint`/anything that creates, edits, posts, sends, transitions or deletes → write). If in doubt, it is a write tool.

Report a table of `server/tool | read or write | why`, and propose the minimal `tools`/`writeTools` for the agent's job. Most of a server's tools should stay out of the agent.
