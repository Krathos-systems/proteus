```
██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝
██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗
██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║
██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝
```

# proteus

[![CI](https://github.com/Krathos-systems/proteus/actions/workflows/ci.yml/badge.svg)](https://github.com/Krathos-systems/proteus/actions/workflows/ci.yml)
![Python 3.15](https://img.shields.io/badge/python-3.15-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)
![mypy](https://img.shields.io/badge/types-mypy%20strict-2A6DB2)
![MCP](https://img.shields.io/badge/tools-MCP-000000)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

**Turn an event into an AI agent run.** Something happens in a tool you already use (an issue is created, a pull request is opened, a form is submitted, an alert fires) and it sends a webhook. Proteus checks the webhook, builds a prompt from it, and hands the job to a coding-agent CLI. That CLI then reads and acts through the tools you allow: it can comment on the issue, review the pull request or summarise the alert.

You write the agent once, as a small directory of JSON and Markdown. It runs unchanged on **GitHub Copilot CLI, Claude Code, Gemini CLI, Codex or pi**, and the `HARNESS` env var picks one. There is no agent framework to learn and no code to write.

```
 Jira, GitHub, a form,     POST /<agent>/webhook        proteus                              harness CLI
 a monitoring alert   ──────────────────────────────▶  1. check the shared secret  ──────▶  claude / copilot /
                           {"key": "BUG-42", ...}       2. validate every field            gemini / codex / pi
                                                        3. fill in the prompt                  │
                                                        4. queue the job (one at a time)       │ only the MCP tools
                                                                                               ▼ you listed
                                                                                        Jira, GitHub, a database …
```

### What you can build
Anything that starts from an event and can be done by reading and calling a few tools. For example:

- **Triage new bugs.** When a Jira bug is created, read it, find duplicates and missing details, and post a comment.
- **Review pull requests.** When a pull request opens, read the diff and its ticket, and post a short review.
- **Estimate stories.** When a story moves to "Ready", estimate the effort and list the open questions.
- **Explain alerts.** When an alert fires, read the recent logs through an MCP server and post a likely cause to chat.
- **Answer requests.** When a form is submitted, draft an answer from your docs and post it for a person to check.

### What you get
- **One webhook endpoint per agent**, with a shared secret, strict input validation and a health check.
- **Unattended runs that stay inside limits you set.** An agent can call only the MCP tools you list. Dry-run mode for testing.
- **No lock-in to one AI vendor.** Moving an agent from Claude to Gemini or Codex is a one-line env change.
- **Simple operations.** One Docker image, one container per agent, logs on stdout, and secrets only in the environment.

Each container runs one job at a time and writes the result to its log, so an agent that should leave a trace (a comment, a message) does so through a tool you allow.

## Quick start
Prerequisites: Docker with Compose, an API key for one harness, and [uv](https://docs.astral.sh/uv/) for creating agents and running the tests.

```bash
cp docker-compose.override.EXAMPLE.yml docker-compose.override.yml   # gitignored: set HARNESS and its API key
docker compose up --build hello-agent
curl -X POST localhost:8081/hello/webhook -H 'X-Webhook-Secret: s00p3r-s3cr3t' \
  -H 'Content-Type: application/json' -d '{"name":"Ada"}'
docker compose logs hello-agent   # the job result is written to the log
```

`hello-agent` (in `examples/`) only writes a greeting, but it has the same structure as every other agent.

## From idea to agent
This section builds a real agent step by step. The idea: *"When someone files a bug in Jira, check it for missing information and comment on the ticket."*

### 1. Answer five questions first
Write the answers down before you write any files. Each one maps onto part of the agent.

| Question | For the bug triager | Goes into |
|---|---|---|
| What event starts it, and which fields does that event send? | Jira "issue created", sending the issue key | `input` in `agent.json` |
| What should the agent do, step by step? | Read the bug, check it for steps to reproduce, expected and actual behaviour, and the affected version, then write a short comment | the skill (`SKILL.md`) |
| What does it need to read? | The Jira issue | `tools` and `mcp.json` |
| What may it change? | It may add a comment and nothing else | `writeTools` |
| Where does the result go? | A comment on the issue | the skill and `writeTools` |

Keep one job per agent. If the answer to "what should it do" has an *and then* in it, consider two agents.

### 2. Create the agent
```bash
uv run python -m runner new bug-triage
```
This copies `examples/hello-agent` to `agents/bug-triage/`:

```
agents/bug-triage/
  agent.json                         what the agent accepts and may do
  skills/bug-triage-skill/SKILL.md   how it does the job
```

### 3. Describe the input and the prompt (`agent.json`)
```json
{
  "pathPrefix": "/bug-triage",
  "skill": "bug-triage-skill",
  "prompt": "Use the {skill} skill to triage Jira bug {key}.",
  "input": {
    "key": { "pattern": "[A-Z][A-Z0-9]+-\\d+" }
  },
  "tools": ["jira/getJiraIssue"],
  "writeTools": ["jira/addOrEditJiraIssueComment"],
  "requiredEnv": ["JIRA_AUTH"],
  "timeoutSeconds": 600
}
```

- Each field in `input` becomes a `{placeholder}` in the prompt. The webhook body must match each `pattern` in full, or it is rejected with `400`. Webhook values end up in the prompt, so keep the patterns tight: a Jira key, an ID or a short title, not free text.
- Keep the prompt short. It says *which* skill to use on *which* thing, and the skill says how.
- List tools as exact `server/tool` names. Tools that only read go in `tools`, and anything that changes something goes in `writeTools`.

### 4. Connect the tools it needs (`mcp.json`)
The agent reaches other systems through [MCP](https://modelcontextprotocol.io) servers. Add `agents/bug-triage/mcp.json`:

```json
{
  "mcpServers": {
    "jira": {
      "url": "https://mcp.atlassian.com/v2/mcp",
      "headers": { "Authorization": "Basic ${JIRA_AUTH}" }
    }
  }
}
```

`${JIRA_AUTH}` is filled in from the environment when the container starts, so the secret never goes into the repo. List it in `requiredEnv`, and the agent refuses to start without it. For this server, `JIRA_AUTH` is `base64("email:api_token")`, made with `echo -n 'email:token' | base64 -w0`, and the token needs the `read:jira-work` and `write:comment:jira` scopes.

To find a server's exact tool names, read its documentation, or connect to it with the MCP Inspector (`npx @modelcontextprotocol/inspector`) and list them.

### 5. Write the instructions (the skill)
`agents/bug-triage/skills/bug-triage-skill/SKILL.md` is where the real behaviour lives. Write it the way you would brief a new colleague who will do the task alone:

```markdown
---
name: bug-triage-skill
description: Checks a new Jira bug for missing information and comments on it. Use when asked to triage a bug.
---

# Bug triage

1. Read the issue named in the prompt with `getJiraIssue`.
2. Check that it has steps to reproduce, the expected and the actual behaviour, and the affected version.
3. Write a comment of at most five lines: thank the reporter, list what is missing as questions,
   and say nothing about what is already there. If nothing is missing, say that it is ready for review.
4. Post it with `addOrEditJiraIssueComment`, then reply with only "posted".
   Never change the issue's fields, status or assignee.
```

Be specific about the output: its length, its format and where it goes. Say what the agent must never do. Keep the front matter `name` equal to the `skill` in `agent.json`.

### 6. Try it in dry run
Add a service to `docker-compose.yml` by copying `hello-agent`:

```yaml
  bug-triage:
    <<: *runner
    environment:
      AGENT: bug-triage
      HARNESS: ${HARNESS:-claude}
    ports:
      - "127.0.0.1:8082:3000"
```

Put the secrets in `docker-compose.override.yml`. Set `DRY_RUN: "true"`, which withholds `writeTools` and has the agent report the comment instead of posting it:

```yaml
  bug-triage:
    environment:
      DRY_RUN: "true"
      WEBHOOK_SECRET: something-long-and-random
      ANTHROPIC_API_KEY: ...
      JIRA_AUTH: ...
```

```bash
docker compose up -d bug-triage
docker compose logs bug-triage          # no CRITICAL line = the agent is valid
curl -X POST localhost:8082/bug-triage/webhook -H 'X-Webhook-Secret: something-long-and-random' \
  -H 'Content-Type: application/json' -d '{"key":"BUG-42"}'
docker compose logs -f bug-triage       # wait for "dry run result:" and read the comment it would post
```

If the agent is misconfigured, the log has one `CRITICAL` line saying what is wrong, and webhooks get `503`. Edit the skill and run `docker compose restart bug-triage` until you like the results; agents are mounted, so there is no rebuild. You can also switch `HARNESS` to compare the harnesses on the same bug.

### 7. Go live and connect the trigger
Set `DRY_RUN: "false"`, deploy the container behind HTTPS (see [Deploying](#deploying)), and point the event at it. In Jira this is an Automation rule:

- **Trigger:** *Issue created*, with the condition *Issue type = Bug*.
- **Action:** *Send web request* to `https://<your-host>/bug-triage/webhook`, method `POST`, header `X-Webhook-Secret: <WEBHOOK_SECRET>`, body `{"key":"{{issue.key}}"}`.

Make sure the agent's own action cannot trigger the rule again. Here, a comment is not an *issue created* event, so this rule is safe.

Any system that can send an HTTP POST with a header can trigger an agent in the same way, such as GitHub webhooks or Actions, GitLab, a monitoring tool or a form backend.

### Tips
- **Start read-only.** Ship with an empty `writeTools` first and read the dry-run results for a while.
- **Watch the cost.** Every webhook is one model run. Keep the trigger narrow (filter in the source system) and set a sensible `timeoutSeconds`.
- **Use a different `WEBHOOK_SECRET` for each agent**, so that one leaked secret does not expose the others.
- **Keep the per-harness model in `models`** (`{"claude": "...", "pi": "anthropic/..."}`), or set `MODEL` for one deployment.

## Agent reference
An agent is a directory under `agents/`: `agent.json`, an optional `mcp.json`, and an optional skill in `skills/<skill>/SKILL.md`.

### agent.json

| Field | Meaning |
|---|---|
| `pathPrefix` | URL prefix of the webhook and healthcheck. Default `/<agent name>`. `PATH_PREFIX` overrides it |
| `prompt` | Prompt template. `{field}` is replaced by the validated input value, `{skill}` by the skill name |
| `input` | Accepted JSON fields. Each needs a `pattern` (a full-match regex: payload values end up in the prompt, so keep them tight); fields are required unless `"required": false`. Unknown fields are ignored |
| `skill` | Name of the skill in `skills/`; its `SKILL.md` front matter `name` must match |
| `tools` | MCP tools the agent may call, as exact `server/tool` entries. Keep them read-only |
| `writeTools` | MCP tools that change something. Withheld when `DRY_RUN=true` |
| `models` | Optional model per harness. The `MODEL` env var overrides it |
| `requiredEnv` | Env vars the agent needs (e.g. for `mcp.json`); missing ones disable the webhook |
| `timeoutSeconds` | The run is killed after this long. Default 600 |

### mcp.json
Uses the common `mcpServers` format, as in [step 4](#4-connect-the-tools-it-needs-mcpjson). A server has either `command` (+ `args`, `env`) for stdio, or `url` (+ `headers`) for streamable HTTP. `${VAR}` placeholders are filled in from the environment at startup. A server starts only if at least one of its tools is in `tools` or `writeTools`. The image has Node and `npx`, so stdio servers published on npm work out of the box.

## Harnesses
Set `HARNESS` to one of the values below, plus that harness's credentials. The runner writes the harness's own config into a private (0700) temp dir at startup, then runs one job at a time.

| `HARNESS` | Credentials (env) | How the agent is restricted |
|---|---|---|
| `copilot` | `COPILOT_GITHUB_TOKEN` (fine-grained PAT, "Copilot Requests") | `--allow-tool server(tool)` per tool, `--no-ask-user`, built-in MCPs off |
| `claude` | `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`) | `--allowedTools mcp__server__tool`, `--permission-mode dontAsk`, `--strict-mcp-config` |
| `gemini` | `GEMINI_API_KEY` | per-server `includeTools`; anything needing approval is denied in headless mode |
| `codex` | `CODEX_API_KEY` or `OPENAI_API_KEY` | per-server `enabled_tools`, `approval_policy = "never"`, read-only sandbox |
| `pi` | the provider's key, e.g. `ANTHROPIC_API_KEY`; set the model as `provider/model` | `--tools read,grep,find,ls,mcp__server__tool…`, built-in MCP with direct tools |

On every harness, only the agent's own MCP servers are loaded, nothing waits for approval, and built-in tools that run commands or write files are not granted. The webhook secret is removed from the harness's environment.

## Environment variables
| Variable | | Notes |
|---|:-:|---|
| `AGENT` | required | Directory name under `AGENTS_DIR` (`/agents` in the image) |
| `HARNESS` | required | `copilot`, `claude`, `gemini`, `codex` or `pi` |
| `WEBHOOK_SECRET` | required | Expected in the `X-Webhook-Secret` header. Use a different value per agent |
| harness credentials | required | See [Harnesses](#harnesses). Not checked at startup; runs fail without them |
| `requiredEnv` of the agent | required | e.g. MCP credentials used in `mcp.json` |
| `DRY_RUN` | optional | `true`: `writeTools` are withheld and the prompt tells the agent to only report what it would do. Default `false` |
| `MODEL` | optional | Overrides the agent's `models` entry |
| `LOG_LEVEL` | optional | `ERROR`, `WARNING`, `INFORMATION` (default) or `DEBUG` |
| `PATH_PREFIX`, `APP_NAME`, `PORT`, `AGENTS_DIR` | optional | Prefix override, name in the startup log line, listen port (3000), agents directory |

If something required is missing or the agent is invalid, the runner still starts and answers the healthcheck, logs one `CRITICAL` line saying what is wrong, and rejects webhooks with `503`.
Logs go to stdout (stderr for warnings and errors). `INFORMATION` logs startup, job start/finish with duration, the dry-run result and errors; `DEBUG` adds rejected/accepted webhooks, the harness command line, its stderr and non-dry-run results. Every env value whose name contains `SECRET`, `PASSWORD`, `TOKEN`, `AUTH`, `KEY` or `CREDENTIAL` is masked as `***` in the logs.

## Webhook API
| Request | Result |
|---|---|
| `GET <prefix>/healthcheck` | `200 ok` (also when unconfigured) |
| `POST <prefix>/webhook` with `X-Webhook-Secret` and a JSON object | `202` accepted; `401` bad secret; `400` invalid/missing field (the body names it); `503` not configured |

Jobs run one at a time in a queue, and results are only written to the container log, so an agent that should act (e.g. comment on an issue) does it through a write tool.

## Deploying
Run one container per agent from the same image, behind any HTTPS reverse proxy that forwards the full path (`<prefix>/*`) to port 3000, with the agent directory mounted at `/agents/<name>`. Give each container its own secrets, and run one replica per agent: a container runs one job at a time, so several replicas would run jobs in parallel.

## Development
```
runner/        the webhook runner (Python 3.15, stdlib only)
  __main__.py    entry: `python -m runner` serves, `python -m runner new NAME` scaffolds an agent
  config.py      env + agent.json/mcp.json loading and validation
  harness.py     per-harness CLI flags and config files
  job.py         payload validation and prompt rendering
  run.py, worker.py, server.py, logger.py, scaffold.py
examples/      hello-agent, the template for `runner new` (no MCP, runs on every harness)
agents/        your agents (mounted into the containers)
tests/         pytest suites (http, invocation, agents, repo)
```

```bash
uv sync
uv run pre-commit install          # once: whitespace/YAML/TOML/JSON checks, ruff and mypy on every commit
uv run ruff check && uv run ruff format --check && uv run mypy runner tests
uv run pytest                      # ~3 s, no Docker, network or credentials
```
Tests are black-box: each starts the real runner on a free port with fake `copilot`/`claude`/`gemini`/`codex`/`pi` binaries that record the arguments, environment and config files they receive. `tests/invocation/test_harness.py` checks, for every harness, the tool allowlist, dry run, MCP translation, skill location and secret handling.

| Command | Area |
|---|---|
| `uv run pytest tests/http` | healthcheck, routing, config errors (503), webhook auth and payload validation |
| `uv run pytest tests/invocation` | per-harness flags and configs, logging and redaction, the one-at-a-time queue, failures and timeouts |
| `uv run pytest tests/agents` | every example boots and runs on every harness; `runner new` |
| `uv run pytest tests/repo` | Dockerfile pins every harness, compose, CI, Python version |

The CI workflow (`.github/workflows/ci.yml`) also builds the image and runs the `bvt` smoke test (`docker compose --profile bvt run --rm bvt`), which checks that every harness CLI starts.

`.claude/skills/` contains developer skills for LLM assistants working on this repo (separate from your agents' runtime skills).

## License
[MIT](LICENSE)
