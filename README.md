# Nautil

<p align="center">
  <strong>A hierarchically recursive agent framework for complex problem solving.</strong>
</p>

<p align="center">
  Nautil structures complex work as a task tree of local solvers.
  Each node can decompose, execute, compose, verify, and escalate within a single recursive control loop.
</p>

<p align="center">
  <a href="https://github.com/Angus07/Nautil-oss/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-0f766e.svg" alt="MIT License"></a>
  <a href="https://angus07.github.io/writing/nautil-hierarchically-recursive-agent-framework/"><img src="https://img.shields.io/badge/blog-core%20write--up-b7791f.svg" alt="Core write-up"></a>
  <a href="https://angus07.github.io/"><img src="https://img.shields.io/badge/site-angus07.github.io-1f2937.svg" alt="Homepage"></a>
</p>

## Overview

Nautil is an **agent control framework** for problems that become hard when planning, execution, state, and failure handling start contaminating one another.

The core idea is simple:

- Represent the problem as a **task tree**
- Treat each node as a **local solver**
- Decompose only into **independent prerequisite tasks**
- Resume the parent once those dependencies return
- Let each node **verify its own result**
- **Escalate** unresolved failure upward to the layer that can restructure the work

This repository contains:

- A **FastAPI backend** that orchestrates node lifecycles and tool execution
- A **React + Vite frontend** that visualizes the task tree, node state, and real-time node logs

## Demo

This section is ready for a short product demo once you record it.

For the best GitHub presentation, I recommend:

- A **6-15 second GIF** at the top of the README for instant visual traction
- A **longer MP4 walkthrough** linked from the GIF caption or from Releases

Planned placement:

```text
docs/assets/nautil-demo.gif
docs/assets/nautil-demo.mp4
```

Once those files exist, you can drop this block near the top of the README:

```md
[![Nautil demo](docs/assets/nautil-demo.gif)](docs/assets/nautil-demo.mp4)
```

## Links

- **Core write-up:** [Nautil: A Hierarchically Recursive Agent Framework for Complex Problem Solving](https://angus07.github.io/writing/nautil-hierarchically-recursive-agent-framework/)
- **Personal site:** [angus07.github.io](https://angus07.github.io/)

## Why Nautil

### 1. The structure is easy to see and understand

Nautil makes agent work **visually legible**.

Instead of one opaque loop, the problem appears as a **clear task tree** that feels closer to a mind map:

- You can see how the problem is decomposed
- You can see what each node is doing
- You can see which branches are complete, blocked, or escalating
- You can inspect the reasoning surface of a node without losing the whole structure

That makes the system easier to trust, easier to debug, and easier to use on problems that would otherwise become unreadable.

### 2. Human-AI collaboration is natural

Nautil is designed for **human-in-the-loop problem solving**, not just autonomous execution.

The product flow makes collaboration straightforward:

- Review the draft structure before execution
- Approve or reject decomposition decisions
- Pause execution at any time
- Inspect a node when something looks wrong
- Give feedback to a specific node
- Re-run a node from that point with updated guidance
- Let the agent handle local work while the human steers higher-level structure

This is where the task tree matters as a product, not just as an algorithm. **It gives human judgment a clean place to enter the loop.**

### 3. It works especially well on problems with clear dependency structure

Nautil is strongest when a problem can be expressed as **independent prerequisite tasks plus later integration**.

That makes it a good fit for multi-step work where visibility, intervention, and structured execution matter more than one-shot generation.

## Good Fit Examples

### 1. Personal life guidance with structured exploration

Example: **"How can I find a romantic partner who is truly a good fit for me?"**

### 2. Time-sensitive judgment and decision support

Example: **"Given recent market conditions, is gold still worth investing in now?"**

### 3. Researching and operationalizing a new technology

Example: **"How can I use Claude Code efficiently in real development work?"**

## Runtime Primitives

At runtime, Nautil revolves around five primitives:

- **DECOMPOSE**: identify independent prerequisite tasks
- **EXECUTE**: solve an atomic task directly
- **COMPOSE**: continue the current node after dependencies return
- **VERIFY**: check the current node's own result
- **ESCALATE**: hand unresolved failure upward

## Product Experience

The current UI is built around making the solving process inspectable:

- Submit a problem from the top bar
- Enter **draft planning** before execution
- Review the generated structure
- Approve execution when the tree looks correct
- Inspect any node for:
  - instruction
  - delta state
  - tool calls
  - tool results
  - errors
  - timeline events

## Repository Layout

```text
backend/                    FastAPI backend
backend/core/               Engine, node lifecycle, structural logic, tools
backend/llm/                Provider abstraction
frontend/                   React + Vite UI
searxng/                    Local search configuration
docker-compose.searxng.yml  Optional local SearXNG deployment
.env.example                Environment variable template
LICENSE                     MIT License
```

## Quickstart

### Requirements

- Python 3.10+
- Node.js 20+

### 1. Configure environment

Create your local environment file from the template:

```bash
cp .env.example .env
```

Fill in the keys you need locally. Do not commit `.env`.

### 2. Run the backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Session Controls

The UI can send these controls to the backend per session:

- **Verify mode**
- **Max depth**
- **Max concurrency**
- **Max children**

These let you trade off quality, speed, and exploration breadth.

## Optional Search Setup

If `BRAVE_API_KEY` is not configured, `web_search` can fall back to a local SearXNG instance:

```bash
docker compose -f docker-compose.searxng.yml up -d
```

Then set `SEARXNG_URL` in `.env` to match your local instance.

## Security

- Never commit `.env`
- Provide API keys through environment variables
- Rotate credentials immediately if anything sensitive is exposed

## License

Released under the [MIT License](LICENSE).
