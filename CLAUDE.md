# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Webhook → validated payload → prompt → a harness CLI (`copilot`, `claude`, `gemini`, `codex` or `pi`, picked by `HARNESS`) running the agent's skill with only its allowed MCP tools. One generic Docker image; each agent is a directory (`agent.json`, optional `mcp.json`, `skills/<skill>/SKILL.md`) mounted at `/agents`, one container per agent. `README.md` is the reference for the agent format, env vars, harness table and webhook API.

## Commands

```bash
uv sync                                                      # Python >= 3.15 (.python-version); runtime has no deps, dev tools in uv.lock
uv run ruff check && uv run ruff format --check && uv run mypy runner tests   # mypy is --strict
uv run pre-commit install                                    # once; hooks run ruff/mypy from uv.lock plus file hygiene checks
uv run pytest                                                # all tests, parallel (-n 4 from pyproject), ~3 s
uv run pytest tests/http                                     # one area: http | invocation | agents | repo
uv run pytest -n0 tests/http/test_webhook.py -k <text>       # one test, no xdist
uv run python -m runner new <name>                           # scaffold agents/<name> from examples/hello-agent
AGENTS_DIR=examples AGENT=hello-agent HARNESS=claude WEBHOOK_SECRET=x uv run python -m runner   # run without Docker
docker compose build hello-agent && docker compose --profile bvt run --rm bvt                   # image + smoke test (as CI)
```

Local Docker runs need `docker-compose.override.yml` (gitignored, copied from `docker-compose.override.EXAMPLE.yml`) for `HARNESS`, its key and secrets. Keep `DRY_RUN: "true"` there unless real writes are explicitly wanted.

## Architecture

- **Config is loaded at import time.** `runner/config.py` reads env and `agents/<AGENT>/agent.json` + `mcp.json` into module globals (`agent`, `HARNESS`, `PREFIX`, `config_errors`, …). `runner/run.py` likewise calls `harness.prepare()` at import. This is why tests spawn the runner as a subprocess rather than importing it.
- **Config errors never crash the process.** Validation appends to `config_errors`; the server still starts, answers `GET <prefix>/healthcheck`, logs one `CRITICAL` line and answers webhooks with `503`. Preserve this when adding validation.
- **`runner/harness.py`** translates the neutral agent (prompt, `server/tool` allowlist, MCP servers, skill, model) into each harness's flags/config files inside a private 0700 temp dir. `ADAPTERS` maps harness → adapter; `SKILLS_DIR` sets where skills are copied in the workspace (`.github/skills`, `.claude/skills`, else `.agents/skills`). MCP servers with no allowed tools are dropped. Every adapter must keep the same guarantees: only the agent's MCP servers, only listed tools, no approval prompts, no built-in tools that run commands or write files.
- **`runner/job.py`** validates the payload (each `input` field's `pattern` is a full match) and renders the prompt; `DRY_RUN` withholds `writeTools` and appends a dry-run note.
- **`runner/run.py`** runs the harness with cwd = the workspace and `WEBHOOK_SECRET` stripped from its env. **`runner/worker.py`** runs jobs strictly one at a time from a queue; results go only to the log. `server.py` is stdlib `http.server` routing + secret check; `scaffold.py` implements `runner new`.
- **Logging** (`runner/logger.py`): values of env vars whose name contains `SECRET|PASSWORD|TOKEN|AUTH|KEY|CREDENTIAL` are redacted as `***` automatically.

### Tests

Black-box: the `start_server` fixture in `tests/conftest.py` starts the real `python -m runner` on a free port against a temp agents dir, with fake harness binaries on `PATH` (the `RECORDER` script) that log args, env, cwd, config files and skill locations they receive. No Docker, network or credentials. `tests/repo/test_consistency.py` asserts repo-level invariants (Dockerfile pins every harness CLI, bvt checks every harness, compose ports unique and agents mounted read-only, CI steps, Python version, no runtime deps), so changing those files may need a test update.

A harness change needs a case in `tests/invocation/test_harness.py`. Adding a harness touches: `HARNESSES` in `runner/config.py` and `tests/conftest.py`, `ADAPTERS`/`SKILLS_DIR` in `runner/harness.py`, a pinned `*_VERSION` in the `Dockerfile`, the `bvt` command in `docker-compose.yml`, and the README harness table.

## Conventions

- Runtime code is **stdlib-only** (enforced by a repo test). Fully typed for `mypy --strict`; ruff with single quotes, line length 120.
- Agents: every `input` field gets a tight full-match `pattern` (values land in the prompt); `tools` are exact `server/tool`, minimal and read-only; anything that changes something goes in `writeTools`. Runs are unattended. An agent's skill front matter `name` must equal `skill` in `agent.json`.
- Harness CLI versions are pinned in the `Dockerfile`; bump deliberately and run the bvt.
- If a test fails because behaviour changed on purpose, tell the user rather than silently editing the test.
- When behaviour changes, keep README, this file and `.claude/skills/` in sync (`docs-sync` skill).
