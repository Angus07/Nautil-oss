# Nautil

Nautil is a **hierarchically recursive agent framework** that structures complex problem solving as a **task tree** of local solvers.

This repository contains:

- A **FastAPI backend** that orchestrates node lifecycles (decompose → execute/compose → optional verify → escalate/retry)
- A **React + Vite frontend** that visualizes the task tree, node status, and real-time node logs

## Links

- Blog (core write-up): `https://angus07.github.io/writing/nautil-hierarchically-recursive-agent-framework/`
- Homepage: `https://angus07.github.io/`

## What makes Nautil different

### Hierarchically recursive control (task tree)

Complex work is represented as a **tree**. Each node is a local solver with its own instruction, context, and result. When a node is not atomic, it **decomposes** into independent child tasks that can run in parallel.

### Five primitives (implementation-aligned)

At runtime, nodes follow a unified loop:

- **DECOMPOSE**: create independent sub-tasks (children)
- **EXECUTE**: solve an atomic task directly
- **COMPOSE**: integrate child results to finish the parent task
- **VERIFY** (optional): verify result quality (can be disabled for faster demos)
- **ESCALATE**: bubble failure upward (parent may restructure or partially deliver)

### Key design principle (important)

Each node must **focus on solving its own current task**. The parent/ancestor chain is provided only as background context — **do not get pulled off-track by upstream goals**.

## Demo UX overview

- Submit a problem in the top bar
- The system enters **draft planning** (decomposition only) and pauses leaf nodes for review
- Click **Approve** to enter execution phase
- Click any node to inspect:
  - **Instruction**
  - **Delta State (ΔState)** (e.g. verification feedback on retry)
  - **Execution timeline** (tool calls / tool results / errors)

## Repo layout

```text
backend/      FastAPI backend (engine + tools)
frontend/     React + Vite frontend (graph UI)
.env.example  environment variable template (DO NOT commit .env)
LICENSE       MIT License
```

## Quickstart (local development)

### 1) Requirements

- Node.js 20+
- Python 3.10+

### 2) Configure environment

Create your local `.env` from the template:

```bash
cp .env.example .env
```

Fill in keys in `.env` as needed (never commit `.env`).

### 3) Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration knobs (UI → backend)

The UI can submit these parameters per session:

- **Verify mode**: verify each node result (slower, higher quality) vs fast mode (skip verification)
- **Max depth**: max decomposition depth
- **Max concurrency**: max concurrent node processing
- **Max children**: max children created in a single decompose

## Optional: Search engine for `web_search`

If you don't set `BRAVE_API_KEY`, `web_search` can fall back to a local SearXNG instance.

```bash
docker compose -f docker-compose.searxng.yml up -d
```

Set `SEARXNG_URL` in `.env` to match your instance (see `.env.example`).

## Security / secrets

- **Never commit** `.env`.
- API keys must be provided via environment variables.
- If you find any leaked secrets, remove them immediately and rotate credentials.

## License

MIT — see `LICENSE`.
