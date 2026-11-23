---
name: smoke-test
model: claude-haiku-5-5
description: Run the proteus bvt smoke test (every harness CLI starts, runner answers its healthcheck). Use when asked to smoke test or verify the image, as CI does.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. If the image is missing or stale, run the `docker-build` skill steps first.
2. Run `docker compose --profile bvt run --rm bvt` (as CI does): every harness CLI prints its version and the runner answers `GET /hello/healthcheck`.
3. Report pass/fail, each CLI version printed, and on failure the first error.
