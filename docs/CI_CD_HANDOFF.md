# CI/CD Handoff — Stimm Publishing & Docker

This document provides everything needed to set up GitHub Actions workflows for publishing the Stimm project's three distributable artifacts. All work is on the **`v2` branch** (to be merged into `main`).

## Repository

- **URL:** `https://github.com/stimm-ai/stimm`
- **Branch:** `v2`
- **Existing CI:** `.github/workflows/ci.yml` — lint (ruff, bandit, semgrep, pip-audit) + test (pytest with Docker services). Currently targets `main` only; needs updating to cover `v2`/tags.

---

## 1. PyPI Publish — `stimm` (Python)

### Package Info

| Field | Value |
|---|---|
| Name | `stimm` |
| Version | `0.1.0` |
| Source | `pyproject.toml` (root) |
| Build system | `hatchling` |
| Package dir | `src/stimm/` |
| Python | `>=3.10` |

### Build & Publish Commands

```bash
# Install build tools
pip install build twine

# Build sdist + wheel
python -m build

# Upload to PyPI
twine upload dist/*
```

Or using the trusted publisher workflow (preferred):

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    # No token needed if trusted publisher is configured on PyPI
    # Otherwise use:
    password: ${{ secrets.PYPI_TOKEN }}
```

### Trigger

Tag-based: `v*` (e.g., `v0.1.0`). The version in `pyproject.toml` must match the tag.

### Required Secrets

| Secret | Description |
|---|---|
| `PYPI_TOKEN` | PyPI API token (or configure [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) on PyPI for tokenless auth) |

### Workflow Outline

```yaml
name: Publish Python Package

on:
  push:
    tags: ["v*"]

jobs:
  publish-pypi:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### Verification

```bash
pip install stimm==0.1.0
python -c "from stimm import VoiceAgent; print('OK')"
```

---

## 2. npm Publish — `@stimm/protocol` (TypeScript)

### Package Info

| Field | Value |
|---|---|
| Name | `@stimm/protocol` |
| Version | `0.1.0` |
| Source | `packages/protocol-ts/` |
| Entry | `dist/index.js` |
| Types | `dist/index.d.ts` |
| Module | ESM (`"type": "module"`) |
| Build | `tsc` |
| Published files | `dist/`, `src/` |
| Dependency | `livekit-client ^2.0.0` |

### Build & Publish Commands

```bash
cd packages/protocol-ts
npm install
npm run build     # tsc → dist/
npm publish --access public
```

### Trigger

Same tag as PyPI: `v*`. Version in `packages/protocol-ts/package.json` must match.

### Required Secrets / Trusted Publisher

Prefer **Trusted Publishers** (no token needed):

| Champ | Valeur |
|---|---|
| Organization or user | `stimm-ai` |
| Repository | `stimm` |
| Workflow filename | `release.yml` |
| Environment name | *(leave blank)* |

Configure at: npmjs.com → Packages → `@stimm/protocol` → Settings → **Trusted publishing**

Fallback: set `NPM_TOKEN` secret if tokens are still needed.

### Workflow Outline

```yaml
name: Publish npm Package

on:
  push:
    tags: ["v*"]

jobs:
  publish-npm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          registry-url: "https://registry.npmjs.org"
      - name: Install & Build
        working-directory: packages/protocol-ts
        run: |
          npm install
          npm run build
      - name: Publish
        working-directory: packages/protocol-ts
        run: npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### Verification

```bash
npm info @stimm/protocol version
# Should output: 0.1.0
```

---

## 3. Docker Image — `ghcr.io/stimm-ai/stimm-agent`

### Context

The Docker image packages a reference voice agent that depends on the `stimm` Python package. The Dockerfile and agent source currently live in the **openclaw** repo at `extensions/stimm-voice/python/`, but should be **copied into this repo** for the CI workflow.

### Recommended: Add Dockerfile to Stimm Repo

Create `docker/agent/` in this repo:

```
docker/agent/
├── Dockerfile
├── agent.py
└── requirements.txt
```

#### `docker/agent/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

CMD ["python", "agent.py", "start"]
```

#### `docker/agent/requirements.txt`

```
stimm[deepgram,openai]>=0.1.0
```

#### `docker/agent/agent.py`

```python
"""Reference Stimm voice agent for Docker deployment."""

import os
from livekit.agents import WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero
from stimm import VoiceAgent

agent = VoiceAgent(
    stt=deepgram.STT(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    fast_llm=openai.LLM(model=os.environ.get("STIMM_LLM_MODEL", "gpt-4o-mini")),
    buffering_level=os.environ.get("STIMM_BUFFERING", "MEDIUM"),
    mode=os.environ.get("STIMM_MODE", "hybrid"),
    instructions=(
        "You are a friendly and helpful voice assistant. "
        "Keep responses concise and conversational. "
        "When the supervisor sends you instructions, incorporate them naturally."
    ),
)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=agent.entrypoint))
```

### Image Details

| Field | Value |
|---|---|
| Registry | GitHub Container Registry (GHCR) |
| Image | `ghcr.io/stimm-ai/stimm-agent` |
| Tags | `latest` + version tag (e.g., `0.1.0`) |
| Base | `python:3.12-slim` |
| Build context | `docker/agent/` |

### Trigger

Same tag as the others: `v*`.

### Required Permissions

GHCR uses `GITHUB_TOKEN` — no additional secrets needed, but the job needs `packages: write` permission.

### Workflow Outline

```yaml
name: Publish Docker Image

on:
  push:
    tags: ["v*"]

jobs:
  publish-docker:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract version from tag
        id: version
        run: echo "version=${GITHUB_REF_NAME#v}" >> "$GITHUB_OUTPUT"

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: docker/agent
          push: true
          tags: |
            ghcr.io/stimm-ai/stimm-agent:latest
            ghcr.io/stimm-ai/stimm-agent:${{ steps.version.outputs.version }}
```

### Verification

```bash
docker pull ghcr.io/stimm-ai/stimm-agent:0.1.0
docker run --rm ghcr.io/stimm-ai/stimm-agent:0.1.0 python -c "from stimm import VoiceAgent; print('OK')"
```

---

## Unified Workflow (Recommended)

All three artifacts share the same trigger (`v*` tag) and can be combined into a single workflow file at `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  # Run existing tests first
  test:
    uses: ./.github/workflows/ci.yml

  publish-pypi:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1

  publish-npm:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", registry-url: "https://registry.npmjs.org" }
      - working-directory: packages/protocol-ts
        run: npm install && npm run build
      - working-directory: packages/protocol-ts
        run: npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}

  publish-docker:
    needs: [publish-pypi]  # Wait for stimm to be on PyPI before Docker build
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: version
        run: echo "version=${GITHUB_REF_NAME#v}" >> "$GITHUB_OUTPUT"
      - uses: docker/build-push-action@v6
        with:
          context: docker/agent
          push: true
          tags: |
            ghcr.io/stimm-ai/stimm-agent:latest
            ghcr.io/stimm-ai/stimm-agent:${{ steps.version.outputs.version }}
```

**Key:** `publish-docker` depends on `publish-pypi` because the Docker build does `pip install stimm[deepgram,openai]>=0.1.0` — the package must be on PyPI first.

---

## Required GitHub Secrets Summary

| Secret | Where | Notes |
|---|---|---|
| `NPM_TOKEN` | Repository Settings → Secrets | Only if NOT using npm trusted publishers |
| `PYPI_TOKEN` | Repository Settings → Secrets | Only if NOT using PyPI trusted publishers |
| `GITHUB_TOKEN` | Built-in | Automatic, needs `packages: write` permission in job |

---

## Existing CI Updates Needed

The current `.github/workflows/ci.yml` targets only `main` branch. It needs:

1. **Branch trigger**: Add `v2` (or `push.branches: [main, v2]`) so tests run on v2 pushes
2. **Tag trigger**: Add `push.tags: [v*]` so the reusable workflow call in `release.yml` works
3. **Remove v1 lint-front job**: The `lint-front` job references `src/front/` which no longer exists in v2 (the v1 Next.js frontend was removed). Delete this job.
4. **Update test job docker-compose**: The v2 `docker-compose.yml` only has a `livekit` service (no postgres/redis). Simplify the service startup step.

---

## File Checklist

Before running the release workflow, ensure these files are in place:

- [x] `docker/agent/Dockerfile` — copy from openclaw or create per above
- [x] `docker/agent/agent.py` — copy from openclaw or create per above
- [x] `docker/agent/requirements.txt` — `stimm[deepgram,openai]>=0.1.0`
- [x] `.github/workflows/release.yml` — new unified release workflow
- [x] `.github/workflows/ci.yml` — updated triggers, removed v1 jobs
- [x] `scripts/bump-version` — atomic version bump script (both files at once)
- [ ] GitHub repo secrets configured (`NPM_TOKEN`, `PYPI_TOKEN`) — only needed if NOT using trusted publishers
- [ ] PyPI trusted publisher configured — `stimm-ai/stimm`, workflow `release.yml`
- [ ] npm trusted publisher configured — `stimm-ai/stimm`, workflow `release.yml`
- [ ] Versions in `pyproject.toml` and `packages/protocol-ts/package.json` match the tag

---

## Release Process

Versions in `pyproject.toml` and `packages/protocol-ts/package.json` are kept in sync by `scripts/bump-version`. The `release.yml` workflow enforces this with a `check-versions` gate — a mismatch fails the workflow immediately before tests run.

```bash
# 1. Bump both versions atomically
scripts/bump-version 0.2.0

# 2. Commit and push the version bump FIRST
git add pyproject.toml packages/protocol-ts/package.json
git commit -m "chore: release v0.2.0"
git push origin v2

# 3. Tag HEAD and push tag to trigger the release workflow
git tag v0.2.0 HEAD
git push origin v0.2.0
```

> **Important:** always push the version-bump commit before the tag. The `check-versions` job reads the files at the tagged commit — if the tag points to a commit before the bump, versions won't match.

The pipeline: `check-versions` → `test` → `publish-pypi` + `publish-npm` → `publish-docker`.
