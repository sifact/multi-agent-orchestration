---
title: Contoso Aero Engines Assistant
description: A router baseline and modular-monolith coordinator for a synthetic engine-support assistant.
---

## Contoso Aero Engines assistant: router and coordinator

**Live demo:** https://contoso-aero-playground.vercel.app

A question-answering assistant for Contoso Aero Engines, a fictional jet-engine maker. It supports
two orchestration patterns in one modular monolith and documents a third, future deployment
version. All versions share the same data, agent interface and frozen test set.

| Version | Pattern | Status |
|---|---|---|
| V1 | One intent call routes each question to one agent | Measured baseline |
| V2 | A coordinator plans and sequentially dispatches up to three agent steps, then synthesizes multi-step answers | Modular-monolith preview |
| V3 | Coordinator over agent microservices | Future project |

## Dataset

The engine telemetry is real NASA C-MAPSS data (subset FD003). Everything else (fleet, production, quality, service and documents) is synthetic and linked to it. See [data/SOURCES.md](data/SOURCES.md) for provenance and the planted stories.

```bash
uv sync
uv run python -m contoso_aero.data    # needs data/raw/cmapss (see data/SOURCES.md)
```

This writes:

* `data/generated/contoso_aero.sqlite3` and CSV copies. These are git-ignored because they contain NASA data.
* The knowledge documents in `data/knowledge/`.

## Ask a question

Create `.env` in this folder with the same values `nl-to-sql` uses (it is git-ignored):

```text
NL_SQL_BASE_URL=...
NL_SQL_API_KEY=...
NL_SQL_MODEL=...
```

```bash
uv run contoso-aero "Which supplier lot is in quarantine and why?"
```

Router (auto) remains the default: one intent call selects at most one agent, and `unsupported`
is refused without an agent call. Coordinator (v2, preview) replaces intent detection with one
planning call, runs one to three steps sequentially, and synthesizes only when there are multiple
steps. Both orchestration graphs use LangGraph; each agent's tool loop is plain Python
(`agents/common/loop.py`). Agents remain framework-free, do not import each other, and are called
through `handle(question, context) -> AgentReply`. `tests/test_agents.py` enforces that boundary.
The hand-written model client records tokens, model time and rate-limit wait per call.


### Browser playground

```bash
uv run contoso-aero-ui            # http://127.0.0.1:8010
```

Choose Router (auto), Coordinator (v2, preview), or send a question straight to one agent to test
it without orchestration. Coordinator mode shows the numbered plan, each step's agent, answer and
tool calls, plus the synthesis result when used. The page also shows time spent waiting on rate
limits versus model time. Locally it listens on loopback only. The public demo runs the router
handler on Vercel, where the model key stays in the server's environment and never reaches the
page.

An About tab explains the project and its three-version roadmap for non-technical readers. The page opens in a dark theme, and the theme toggle switches to light and remembers the choice.

### Deploying the public demo

The demo runs on Vercel as one Python function (`deploy/vercel/api/index.py`) that wraps the same handler. The build script stages the package, the knowledge documents and a copy of the database with the `ground_truth` answer key removed; these staged copies are git-ignored and uploaded straight from your machine, because they contain NASA data.

```bash
deploy/vercel/build.sh
cd deploy/vercel && vercel deploy --prod
```

The model settings (`NL_SQL_BASE_URL`, `NL_SQL_API_KEY`, `NL_SQL_MODEL`) are stored as encrypted environment variables in the Vercel project, not in any file. The demo is public, so every question spends the free-tier model quota.

## Datasets: test set and dev set

| Set | File | Size | Role |
|---|---|---:|---|
| Test set | `data/eval/questions.jsonl` | 59 | Frozen release gate, shared unchanged across all versions |
| Routing dev set | `data/eval/routing_probe.jsonl` | 19 | Hand-written questions used to tune and check V1 routing |
| Coordination dev set | `data/eval/coordination_probe.jsonl` | 19 | Hand-written questions used to tune and check V2 planning |

* Tune prompts and agents only against the relevant dev set. Never edit the test set to make a run pass.
* `uv run python -m contoso_aero.evaluation.probe --repeat 3` probes router intent only.
* `uv run python -m contoso_aero.evaluation.plan_probe --repeat 3` probes the coordinator planner only. These probes do not dispatch agents or run the full evaluation.

## Run the evaluation

The frozen corpus contains 59 questions: 24 single-agent, 23 multi-agent and 12 unsupported.
Multi-agent rows intentionally score routing as incorrect for V1; V2 is scored by whether the
agents it called match the expected set.

```bash
uv run python -m contoso_aero.evaluation.runner
uv run python -m contoso_aero.evaluation.report data/eval/runs/latest.json
```

The runner defaults to `--pipeline router`. Use `--pipeline coordinator` for V2; its output uses a
separate filename so it cannot overwrite a router run.

The runner writes per-question JSON with exact routing accuracy, answer facts and numeric tolerances,
correct refusals, intent/agent/total latency, rate-limit wait, tool calls and token counts. The report
writes `data/eval/runs/latest.md`. Run outputs are local evaluation artifacts and are ignored by Git.
