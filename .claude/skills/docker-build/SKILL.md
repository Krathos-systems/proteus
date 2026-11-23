---
name: docker-build
model: claude-haiku-5-5
description: Build the proteus Docker image (one image with every harness CLI) and report the result. Use when asked to build or rebuild the image.
---

**Execution:** delegate this skill to a sub-agent (Agent tool, `subagent_type: general-purpose`, `model: haiku`) with the steps below, and relay its concise result. Do not run it in the main session. If you are already running as a sub-agent, do not delegate again: run the steps directly.

1. Run `docker compose build hello-agent` from the repo root (the one image every agent uses; harness CLI versions are pinned in the `Dockerfile`).
2. Report success with the image tag (`proteus:latest` unless `tag` is set), or the failing build step and its last error lines. Do not change pinned versions to make it pass.
