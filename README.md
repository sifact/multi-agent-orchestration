# Contoso Aero Engines assistant: router baseline

**Live demo:** https://contoso-aero-playground.vercel.app

A question-answering assistant for Contoso Aero Engines, a fictional jet-engine maker. It is built as a **router pattern inside a modular monolith**: a separate intent-detection call picks exactly one agent module to answer each question. It recreates the original architecture described in Microsoft ISE's [Orchestration Patterns for Multi-Agent Systems](https://devblogs.microsoft.com/ise/coordinator-patterns-multi-agent-systems/). A separate project will rebuild it with coordinators over agent microservices, using the same data and evaluation set.

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

Each question goes through one intent-detection call, a lookup-table router, and exactly one agent
module (`telemetry`, `service`, `production`, `quality` or `knowledge`); `unsupported` is refused
without calling an agent. The request pipeline is a LangGraph graph
(`routing/graph.py`); each agent's tool loop is plain Python (`agents/common/loop.py`), so agent
modules carry no framework into project 2. Only the router's control flow uses LangGraph, and the model client stays hand-written so
tokens, model time and rate-limit wait are measured per call. Agent modules never import each other,
which `tests/test_agents.py` enforces.


### Browser playground

```bash
uv run contoso-aero-ui            # http://127.0.0.1:8010
```

Ask through the router, or send a question straight to one agent to test it without intent detection. The page shows which agent was picked, the answer, the time spent waiting on rate limits versus model time, and every tool call with its SQL and output. Locally it listens on loopback only. The public demo runs the same handler on Vercel, where the model key stays in the server's environment and never reaches the page.

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
| Test set | `data/eval/questions.jsonl` | 59 | Frozen release gate, shared unchanged with project 2 |
| Routing dev set | `data/eval/routing_probe.jsonl` | 19 | Hand-written questions used to tune and check the router |

* Prompts and agents are tuned only against the dev set. The test set is never edited to make a run pass.
* A router fix counts only if the dev probe passes with repeats (`uv run python -m contoso_aero.evaluation.probe --repeat 3`) and the test set does not regress.
* The dev set calls only intent detection, so a probe run costs a few thousand tokens instead of a full evaluation.

## Run the evaluation

The shared corpus contains 59 questions: 24 single-agent, 23 multi-agent and 12 unsupported.
Multi-agent rows intentionally score routing as incorrect for this one-agent baseline; that is the
capability gap project 2 is expected to address.

```bash
uv run python -m contoso_aero.evaluation.runner
uv run python -m contoso_aero.evaluation.report data/eval/runs/latest.json
```

The runner writes per-question JSON with exact routing accuracy, answer facts and numeric tolerances,
correct refusals, intent/agent/total latency, rate-limit wait, tool calls and token counts. The report
writes `data/eval/runs/latest.md`. Run outputs are local evaluation artifacts and are ignored by Git.
