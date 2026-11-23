# syntax=docker/dockerfile:1
# One generic image with every supported harness. Agents are mounted at /agents;
# AGENT picks one and HARNESS picks the CLI that runs it.

# The harness CLIs are npm packages, so the image carries Node next to Python.
FROM node:26-slim AS node

FROM python:3.15-slim
ARG COPILOT_VERSION=1.0.114
ARG CLAUDE_VERSION=2.1.330
ARG GEMINI_VERSION=0.70.0
ARG CODEX_VERSION=0.171.0
ARG PI_VERSION=1.6.0

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
# Node's shared libraries are not in the python slim image; git is used by several harnesses.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libatomic1 libstdc++6 git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && npm install -g --prefix /usr/local \
      "@github/copilot@${COPILOT_VERSION}" \
      "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
      "@google/gemini-cli@${GEMINI_VERSION}" \
      "@openai/codex@${CODEX_VERSION}" \
      "@earendil-works/pi-coding-agent@${PI_VERSION}" \
 && npm cache clean --force \
 && rm -rf /root/.npm /tmp/* \
 && useradd --create-home --uid 1000 app

WORKDIR /app
COPY runner/ ./runner/

USER app
ENV AGENTS_DIR=/agents PORT=3000 PYTHONUNBUFFERED=1
EXPOSE 3000
HEALTHCHECK --start-period=10s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/healthcheck', timeout=5)"]
CMD ["python", "-m", "runner"]
