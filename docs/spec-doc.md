# Contoso Aero Engines assistant: requirements specification

Three-version plan: a router baseline, a coordinator in a modular monolith, then a coordinator
over agent microservices.

| Field | Value |
|---|---|
| Status | Version 1 is the measured baseline; version 2 is implemented in the modular monolith; version 3 is future work |
| Repository | <https://github.com/sifact/multi-agent-orchestration> (public) |
| Source article | Microsoft ISE, "Orchestration Patterns for Multi-Agent Systems" (Lily Jia, 12 June 2026): <https://devblogs.microsoft.com/ise/coordinator-patterns-multi-agent-systems/> |
| Roadmap | Version 1: router; version 2: modular-monolith coordinator; version 3: coordinator over agent microservices |
| Last updated | 2026-11-03 |

## 1. Purpose

In the ISE article, a client's production chatbot used a **router pattern inside a modular monolith**:

* A separate intent-detection LLM call labelled each question.
* A router then sent it to **exactly one** agent module.
* Everything lived in one app, one codebase and one deployment.

ISE later moved the client to coordinators over agent microservices, and found that the coordinator adds latency.

Version 1 rebuilds the **original** architecture faithfully as a **measured baseline**. Version 2 adds a coordinator in the same modular monolith. Version 3 is a future project that moves agents behind microservices. The versions use the same data and frozen test set so they can be compared on:

* answer quality
* routing
* latency
* cost

**Audience:** a Microsoft manufacturing and mobility team. The domain is therefore the "digital thread" from the factory (production and quality) to the fleet (engines in service).

## 2. Scope

### In scope

* A question-answering assistant for **Contoso Aero Engines**, a fictional jet-engine maker that builds the CX-7 engine.
* Version 1: one intent-detection call, a lookup-table router, five agent modules and a refusal path.
* Version 2: a planner, sequential dispatcher and optional synthesizer over the same five agent modules.
* A reproducible dataset: real NASA telemetry, plus synthetic factory, fleet and document data linked to it.
* A portable evaluation set and harness, reused unchanged across all three versions.
* A command-line tool and a local browser playground for manual testing.

### Out of scope (non-goals)

* Agent microservices, a gateway and cloud deployment. These are version 3 work; versions 1 and 2 remain a modular monolith.
* Any real manufacturer's name or internal data. No defense or export-controlled content.
* Real FAA airworthiness directives in the knowledge base. All 10 documents are synthetic.
* Azure safety and red-team evaluators, which need an Azure project.

## 3. Architecture

Version 1 keeps the original one-agent router:

```text
question ─► intent detection (1 LLM call, 1 label)
              │
              ▼
           router (dict lookup)
     ┌──────┬────────┬──────────┬────────┬───────────┐
 telemetry service production quality knowledge   unsupported
     │      │        │          │        │             │
     └──────┴── one agent answers ───────┘        refusal text
                      │
                      ▼
               answer returned as-is (no merge, no second agent)
```

Version 2 plans one to three steps in one model call, runs them sequentially through the route
table, and synthesizes only when the plan has multiple steps:

```text
question ─► planner (1 LLM call)
              │
        unsupported ─► fixed refusal (no agent)
              │
          1 to 3 steps
              ▼
       sequential dispatcher ─► ROUTES ─► handle(question, context)
              │                       └── prior findings for dependent steps
              ▼
       one step: return answer unchanged
       multiple steps: synthesize from step answers, label sources and missing parts
```

| Component | Location | Responsibility |
|---|---|---|
| Intent detection | `routing/intent.py` | One model call that returns exactly one of `telemetry`, `service`, `production`, `quality`, `knowledge`, `unsupported`. Anything unparseable becomes `unsupported`. |
| Router | `routing/router.py` | `ROUTES` dict from label to `handle()`; `unsupported` has no route and is refused. |
| Pipeline graph | `routing/graph.py` | LangGraph `StateGraph`: intent node, then a conditional edge to one agent node or the refusal node. Times every stage. |
| Coordinator | `coordination/` | Plans, validates, dispatches and synthesizes a bounded multi-agent run. Calls agents only through `ROUTES` and their existing `handle()` contract. |
| Agent modules | `agents/<name>/` | Each exposes `handle(question, context) -> AgentReply`. |
| Shared agent code | `agents/common/` | Plain-Python tool loop, the read-only SQL tool, and the `AgentContext` / `AgentReply` / `ToolStep` contract. |
| Model client | `llm/client.py` | OpenAI-compatible chat client. Reports tokens, model time and rate-limit wait separately. |
| Data build | `data/` | Builds the SQLite database, CSVs, knowledge documents and evaluation questions. |
| Evaluation | `evaluation/` | Exact evaluators, Azure AI Evaluation SDK harness, runner and report. |
| Interfaces | `cli.py`, `serving/` | Command line and the local browser playground. |

**Version 1's one-agent limitation is intentional and preserved.** Version 2 addresses questions needing multiple agents without changing version 1 behavior. Version 3 changes the deployment boundary, not the agent contract.

## 4. Functional requirements

### Intent and routing

| ID | Requirement |
|---|---|
| FR-1 | Each question gets exactly one intent call that returns exactly one label from the fixed set. |
| FR-2 | The router calls at most one agent per question, through its `handle()` function only. |
| FR-3 | `unsupported` returns a fixed refusal without calling any agent. It covers off-topic, abusive and non-language input, and attempts to change the instructions. |
| FR-4 | Question text is treated as data to classify, never as instructions. Questions are truncated to 2,000 characters for intent. |
| FR-5 | Intent descriptions must cover everything each agent owns. Fixes must describe categories in general terms. Eval question text, IDs or eval-specific names must never appear in the prompt (no overfitting). |

### Agents

| ID | Agent | Data it may use |
|---|---|---|
| FR-6 | Telemetry | `operators`, `aircraft`, `engines`, `engine_telemetry` |
| FR-7 | Service | `removals`, `shop_visits`, `difficulty_reports`, `borescope_inspections` |
| FR-8 | Production | `engine_builds`, `module_builds`, `supplier_lots` |
| FR-9 | Quality | `inspections`, `ncrs`, `deviations`, `lot_quarantines` |
| FR-10 | Knowledge | BM25 search and full-document read over `data/knowledge/*.md` |

| ID | Requirement |
|---|---|
| FR-11 | SQL agents use one `query_sql` tool. It allows only read-only `SELECT` over the agent's own tables, with a 5 s query limit, at most 40 rows and 240 characters per cell. Errors return as text so the model can retry. |
| FR-12 | The tool loop is limited to `max_agent_steps` (default 6). When the limit is reached, the model must answer without tools. |
| FR-13 | A model error ends the agent run and is reported on the reply. It is not raised. |
| FR-14 | Every reply records tokens, model time, retry wait, model and tool call counts, tool outputs (`context`) and a tool trace (tool, arguments, output). |
| FR-15 | No agent can read the `ground_truth` table or `data/eval/questions.jsonl`. |

### Interfaces

| ID | Requirement |
|---|---|
| FR-16 | CLI: `uv run contoso-aero "question" [--json] [--coordinator]`. The default is the version 1 router; `--coordinator` uses version 2 and prints the plan, per-step and synthesis times. |
| FR-17 | Playground: `uv run contoso-aero-ui` serves `http://127.0.0.1:8010`. |
| FR-18 | The playground offers Router (auto), Coordinator (v2, preview) or a direct call to one agent. It shows the selected mode, the answer, the per-stage time split (model vs. rate-limit wait), tokens and each tool call with its SQL and output. Coordinator mode shows numbered plan steps, each step's agent, answer and tools, plus synthesis when used. |
| FR-19 | Locally the playground binds to loopback only. The hosted demo runs the same handler as a Vercel function with the model key held in the server's environment. In both cases it runs one question at a time, limits requests to 4 KB and questions to 1,000 characters, and never returns the API key. |

### Coordinator

| ID | Requirement |
|---|---|
| FR-20 | One planner call returns either `unsupported` with no steps or a plan of one to three steps. Each step has an ID, a known agent, a self-contained question and dependencies on earlier steps. |
| FR-21 | Plan parsing rejects unknown agents, too many steps, forward references, cycles and invalid structures. The planner retries invalid output only the configured number of times; an invalid plan after retries returns an error, never a v1 fallback. |
| FR-22 | Dispatch is sequential and uses only `ROUTES` and `handle(question, context)`. A dependent step receives successful earlier answers as bounded "Findings so far" text. |
| FR-23 | A failed step causes dependent steps to be skipped. Synthesis receives successful answers and missing-step details; the coordinator does not re-plan. |
| FR-24 | A successful one-step plan returns the agent answer without synthesis (after the cleaning in FR-27). A multi-step plan uses one synthesis call, which uses only step answers, identifies each agent's contribution and states what could not be answered. |
| FR-25 | An unsupported plan calls no agent and returns a refusal. Version 1 remains the default pipeline and retains its existing one-agent behavior. |
| FR-26 | The evaluation runner accepts `--pipeline router|coordinator`, defaults to `router`, and writes coordinator runs to a distinct filename. |
| FR-27 | Every model-written string the coordinator passes on or shows (plan questions, agent answers used as findings, the merged answer) is cleaned of look-alike characters: non-breaking and narrow spaces, non-breaking hyphens and the minus sign, zero-width characters and full-width brackets. Models emit these inside identifiers such as `CX7-10041`, where they break database lookups, exact-match scoring and copy-paste. Version 1 output is deliberately left as it was, so the measured baseline does not change. |

## 5. Data requirements

| ID | Requirement |
|---|---|
| DR-1 | **Telemetry is real NASA C-MAPSS, subset FD003.** It has 100 run-to-failure engines (which become removed engines) and 100 test engines (which become the active fleet), with two fault modes (HPC and fan). Source, SHA-256 and citation are in `data/SOURCES.md`. |
| DR-2 | All other data is synthetic and linked by engine serial number (ESN, e.g. `CX7-10114`), supplier lot and date. Difficulty reports follow the FAA Form 8070-1 field layout. |
| DR-3 | Rebuilds are byte-identical: seed `20260612` and a fixed snapshot date of 2026-10-29. |
| DR-4 | Planted stories with known answers support the multi-agent questions:<br>(1) fan blade lot `FBL-2501-117`, deviation `DEV-2025-007`, quarantine, then `SB-CX7-72-0042`<br>(2) torque wrench `TW-118` under-reading, `NCR-2025-0388`, then `SB-CX7-72-0051`<br>(3) trend limits in `CX7-EHM-002`, calibrated on real drift |
| DR-5 | Raw NASA files and the generated database stay local and git-ignored, because they contain NASA data. The knowledge documents and the evaluation questions are committed. |
| DR-6 | `ground_truth` (true remaining life, inferred fault mode, story) is used only for scoring. |

Build command: `uv run python -m contoso_aero.data`. It needs `data/raw/cmapss/` (fetch steps are in `data/SOURCES.md`).

## 6. Evaluation requirements

### Question set

`data/eval/questions.jsonl` holds 59 frozen test questions shared unchanged across all three versions.

| Category | Count | Expectation for this baseline |
|---|---:|---|
| Single-agent | 24 | Router should route and answer correctly |
| Multi-agent | 23 | Version 1 routing scores 0% by design; version 2 is scored against the expected agent set |
| Unsupported | 12 | Must be refused |

Each row records:

* the question
* its category
* the expected agent(s)
* expected facts
* expected numbers with tolerances
* a reference answer
* the expected behaviour (`answer` or `refuse`)

### Datasets: test set and dev set

| Set | File | Size | Role |
|---|---|---:|---|
| Test set | `data/eval/questions.jsonl` | 59 | Frozen release gate, shared unchanged across all versions |
| Routing dev set | `data/eval/routing_probe.jsonl` | 19 | Hand-written questions used to tune and check the version 1 router |
| Coordination dev set | `data/eval/coordination_probe.jsonl` | 30 | Hand-written questions used to tune and check version 2 planning |

* Prompts and agents are tuned only against the relevant dev set. Never edit the test set to make a run pass.
* The router probe tests intent detection; the coordination probe tests planning only. Neither dispatches agents or runs the full evaluation.

### Metrics

**Primary metrics (exact, code-based):**

* routing accuracy
* answer correctness: all expected facts found and all numbers within tolerance
* correct refusals
* latency per stage (intent, agent, total)
* rate-limit wait
* token counts
* 95% Wilson confidence intervals next to each reported rate; rates on fewer than 30 cases are noisy, and overlapping intervals do not establish a change

Version 1 routing uses its existing one-agent scoring rule. When version 2 supplies `predicted_agents`,
routing passes only when the called-agent set matches the expected set; an empty expected set is a
refusal with no agent called.

**Indicative metrics (LLM judge):**

* groundedness: is the answer supported by the agent's tool output? Refusal rows are excluded from this metric.
* relevance
* intent resolution

### Harness decisions

| ID | Decision |
|---|---|
| EV-1 | **Azure AI Evaluation SDK** (`azure-ai-evaluation==1.18.10`, pinned) and its `evaluate()` are the single harness. It runs locally, writes files, and does not require Azure AI Foundry. |
| EV-2 | Exact checks are custom code evaluators with their own unit tests. Built-in judges are `GroundednessEvaluator`, `RelevanceEvaluator` and `IntentResolutionEvaluator`. |
| EV-3 | **The judge uses the same model as the agents.** This was the owner's choice. A model grading its own answers is biased, so every report labels judge scores as indicative. |
| EV-4 | Fact matching ignores case, spacing and typographic hyphens or minus signs (e.g. `CX7‑10052` matches `CX7-10052`). |
| EV-5 | Results are paired to questions by question text, because the SDK returns rows in completion order. Duplicate question texts are rejected. |
| EV-6 | The pipeline target and the judges share one lock, so only one model call is in flight at a time, staying inside the free-tier rate limit. (Setting `PF_WORKER_COUNT=1` deadlocks the SDK and must not be used.) |
| EV-7 | Judge cost is recorded apart from agent cost, so evaluation never pollutes the latency numbers. |
| EV-8 | Each run writes JSON (gitignored, in `data/eval/runs/`) plus a Markdown report with run ID, SDK versions and judge applicability. |

### Running within the free tier ("stay free and split it")

The model is `openai/gpt-oss-120b` on Groq's free tier, which allows:

* 8,000 tokens per minute
* 1,000 requests per day
* about 200,000 tokens per day

The 200,000 daily limit is only visible in 429 responses. A full run with judges does not fit in one day, so the work is split:

| Day | Command | Covers |
|---|---|---|
| Day 1 | `uv run python -m contoso_aero.evaluation.runner --no-judges --output data/eval/runs/baseline-exact.json` | Exact checks on all 59 questions (about 120k tokens) |
| Day 2 | `uv run python -m contoso_aero.evaluation.runner --sample 15 --output data/eval/runs/baseline-judges.json` | Judges on a seeded, category-proportional sample of 15 (6 single, 6 multi, 3 unsupported) |

Render a report with `uv run python -m contoso_aero.evaluation.report <run.json>`.

## 7. Non-functional requirements

| ID | Area | Requirement |
|---|---|---|
| NF-1 | Latency honesty | Every stage is timed by the project itself, not by framework callbacks. Rate-limit wait is recorded separately from model time, and comparisons across versions use model time. |
| NF-2 | Rate limits | 429s are retried using `Retry-After`, up to 8 times. A wait longer than 65 s means the daily quota is used up, so the run fails fast instead of stalling. |
| NF-3 | Security | Keys come from the project's own git-ignored `.env` (`NL_SQL_BASE_URL`, `NL_SQL_API_KEY`, `NL_SQL_MODEL`, optional `NL_SQL_MODEL_TIMEOUT_SECONDS`). Real environment variables override the file. Keys are hidden from `repr` and never committed or logged. |
| NF-4 | Module boundary | Agent modules never import each other. Router and coordinator calls go through `ROUTES` and `handle()`. Tests enforce the boundary, which keeps the contract usable by a future service adapter. |
| NF-5 | Framework boundary | LangGraph wires the router and coordinator graphs. Agent modules import no LangGraph or LangChain code (enforced by a test). |
| NF-6 | Reproducibility | A fixed seed, a fixed snapshot date, a pinned SDK and a recorded `uv.lock`. |
| NF-7 | Code structure | `src/contoso_aero/` is split into stage sub-packages, including `routing/` and `coordination/`, with one responsibility per file and public APIs exported from `__init__.py`. Configuration lives in `config.py`. |
| NF-8 | Module guides | Every core module has `guide/<module>.md`: an H1 file name, a one-line summary, then exactly 5 bullets. A test enforces this, and the guides are kept in sync with the code. |
| NF-9 | Tests | `pytest` uses scripted fake models for offline behavior checks and given/when/then names. `ruff` enforces a 100-character line length. |
| NF-10 | Repository | This project is its own repository with its own `.venv`, `.env` and `.copilot-tracking/` (git-ignored). It shares nothing with `nl-to-sql`. |

## 8. Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Pattern | Version 1: router in a modular monolith; version 2: coordinator in that monolith; version 3: coordinator over agent microservices | Measures routing, coordination and deployment-boundary trade-offs separately |
| Brand | Contoso Aero Engines | Microsoft's standard fictional company; implies no real manufacturer |
| Telemetry | NASA C-MAPSS FD003 | Real data, 100 engines, two fault modes that support two factory stories |
| Language and tooling | Python 3.11+, `uv`, `pytest`, `ruff` | Matches the sibling `nl-to-sql` project |
| Graph framework | LangGraph `StateGraph` for the router and coordinator | Explicit orchestration graphs while keeping agent modules framework-free |
| Agent loop | Plain Python | Keeps agents portable to a future microservice adapter and gives full control of timing |
| Storage | SQLite with a read-only authorizer per agent | Simple, local, enforces table ownership |
| Retrieval | BM25 over Markdown documents | Simple and transparent at 10 documents |
| Model | `openai/gpt-oss-120b` via Groq, OpenAI-compatible | Same endpoint as `nl-to-sql`; free tier |
| Evaluation | Azure AI Evaluation SDK, exact checks plus built-in judges | A library-based, production-style harness that matches the Microsoft audience |
| Judge model | Same as the agents | Owner's choice to stay on the free tier; bias disclosed |
| Budget | Stay on the free tier; split evaluation across days | No paid usage |
| Playground | Standard-library HTTP server and one HTML file | No extra dependencies; runs locally or as one Vercel function |

## 9. Current status

| Area | Status |
|---|---|
| Version 1 dataset, agents, router and CLI | Done |
| Version 1 browser playground and measured baseline | Done |
| Version 2 planner, sequential dispatcher, synthesis and evaluation wiring | Implemented |
| Version 2 browser preview | Implemented; checked in a real browser against real model answers on desktop and phone widths, in both themes |
| Version 2 real-model answers | Five hand-written questions run end to end (three multi-agent, one single-agent, one refusal); every answer matched the database |
| Version 2 planner probe | 26/30 cases passed on three repeats; C06, C10, C13 and C22 failed. No prompt or dev-set changes were made during measurement |
| Repository validation | 108 offline tests and ruff checks pass |
| Version 2 frozen-set gate | Attempted all 59 cases on 2026-11-03; Q036-Q059 recorded endpoint quota errors. The judge batch timed out. This is not a complete release result |
| Version 1 on the V2 model | Not run; the V2 attempt exhausted the model's daily token budget |
| Version 3 microservice deployment | Future work |
| Deployment | No hosted deployment for the coordinator |

### Initial V1 baseline before routing-gap fixes (run `20261030T143443Z`, exact checks, 59 questions, 0 errors)

| Category | Routing | Answers correct | Refusals | Mean total time |
|---|---:|---:|---:|---:|
| Single | 79.2% | 75.0% | n/a | 11.7 s |
| Multi | 0% (by design) | 8.7% | n/a | 20.0 s |
| Unsupported | 100% | n/a | 100% | 1.9 s |
| **All** | 52.5% | 42.6% | 100% | 12.9 s |

* **Most of the measured time is rate-limit waiting.** The mean wait was 9.9 s of the 12.9 s total, against about 3.1 s of model time. 46 of 59 questions waited at least once. All reports must state this.
* **Tokens:** 96,842 in and 23,520 out.

## 10. Known issues

### Historical version 1 single-agent gaps (fixed)

The first baseline exposed gaps that were not the intended one-agent limitation:

The router descriptions were expanded to cover owned data domains and to distinguish explanatory
questions for the knowledge agent from questions about specific records. Production notes now
include plant names derived from the reference data. These changes improved version 1 without
adding labels, multi-agent routing or fallbacks.

### Other notes

* The judge model once returned invalid JSON on a refusal row (HTTP 400). That row is excluded from groundedness anyway. Judge runs use `fail_on_evaluator_errors=False`.
* Some ambiguity is inherent. A question like "Has engine X passed the T50 alert limit?" needs both telemetry and knowledge. That is the intended limit, not something a prompt can fix.

## 11. Cross-version contract

All versions reuse unchanged:

* `data/eval/questions.jsonl` and the scoring rules (evaluators, tolerances and fact normalisation).
* The dataset build (same seed and snapshot date), so answers match.
* The five agent modules and their `handle(question, context) -> AgentReply` contract.
* Model-call and rate-limit accounting, so latency comparisons use model time consistently.

Version 2 adds multi-agent planning and answer synthesis while preserving version 1's router
behavior and default. Agents remain framework-free and do not import each other. The coordinator
calls them only through `ROUTES`; a future version 3 service adapter must preserve the same
`handle()` boundary. Version 3 is expected to add deployment isolation, not to change the agent
contract.

## 12. Remaining work

The version 2 implementation is complete and has been exercised on real model answers, but its
full frozen-set release gate has not completed successfully.

1. Re-run the 59-question coordinator gate after the model quota is available. The 2026-11-03
   attempt recorded quota errors for Q036-Q059 and cannot support final V2 metrics.
2. Run the router on the same model if budget permits. The available V1 reference uses
   `gpt-oss-120b`; it is not directly comparable to the V2 attempt on `gpt-oss-20b`.
3. Rerun the full three-repeat planner probe after quota is available; the latest result was
   26/30, with C06, C10, C13 and C22 failing.
4. Redeploy the hosted demo so it includes the coordinator preview. It still runs version 1 only.

The attempt details and the completed V1 reference are recorded in [the V2 evaluation status](v2-evaluation.md).
No V2 performance or answer-quality result is published on the About page.

Version 3 remains a separate future project.
