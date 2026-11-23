---
name: add-harness
model: claude-opus-5-5
description: Add support for a new coding-agent CLI (harness) to proteus, or change how an existing one is invoked, while keeping the unattended-run guarantees. Use when asked to add, support or change a harness.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: opus`) with the full instructions below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

Every harness must give the same guarantees (see `runner/harness.py` docstring): only the agent's MCP servers load, only the listed MCP tools are allowed, nothing prompts for approval, and no built-in tool may run commands or write files. Find the CLI's flags or config for each one in its docs before writing code; if one cannot be met, stop and tell the user.

## Touch every place
1. `runner/config.py`: add the name to `HARNESSES`.
2. `runner/harness.py`: write `_<name>(agent, state, workspace, servers)` next to the others, reusing `_write_private`, `_stdio_or_http` and `_toml`; register it in `ADAPTERS`; add to `SKILLS_DIR` if the CLI reads skills from somewhere other than `.agents/skills`.
3. `tests/conftest.py`: add to `HARNESSES` and, if the CLI reads its MCP config from a new place, teach `RECORDER` to grab it.
4. `tests/invocation/test_harness.py`: cases for the tool allowlist, dry run, MCP translation, skill location and secret handling, like the existing harnesses.
5. `Dockerfile`: install it pinned with a `*_VERSION` build arg. `docker-compose.yml`: add `<cli> --version` to the `bvt` command.
6. `docker-compose.override.EXAMPLE.yml` (credentials), README "Harnesses" table and env var list, `CLAUDE.md`.

## Verify
`lint`, then `test` (all areas: `tests/repo` checks the Dockerfile pin and bvt), then `docker-build` and `smoke-test` if Docker is available. Report what passed and anything skipped.
