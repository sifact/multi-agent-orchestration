# Contoso Aero Engines assistant: requirements specification

Project 1 of 2: the router-pattern baseline in a modular monolith.

| Field | Value |
|---|---|
| Status | Built; evaluation in progress |
| Repository | <https://github.com/sifact/multi-agent-orchestration> (public) |
| Source article | Microsoft ISE, "Orchestration Patterns for Multi-Agent Systems" (Lily Jia, 12 June 2026): <https://devblogs.microsoft.com/ise/coordinator-patterns-multi-agent-systems/> |
| Companion | Project 2 (coordinators over agent microservices), a separate repository |
| Last updated | 2026-11-02 |

## 1. Purpose

In the ISE article, a client's production chatbot used a **router pattern inside a modular monolith**:

* A separate intent-detection LLM call labelled each question.
* A router then sent it to **exactly one** agent module.
* Everything lived in one app, one codebase and one deployment.

ISE later moved the client to coordinators over agent microservices, and found that the coordinator adds latency.

This project rebuilds the **original** architecture faithfully, so that it can serve as a **measured baseline**. Project 2 will rebuild the same assistant with coordinators over microservices, using the same data and the same evaluation set. The two can then be compared fairly on:

* answer quality
* routing
* latency
* cost

**Audience:** a Microsoft manufacturing and mobility team. The domain is therefore the "digital thread" from the factory (production and quality) to the fleet (engines in service).

## 2. Scope

### In scope

* A question-answering assistant for **Contoso Aero Engines**, a fictional jet-engine maker that builds the CX-7 engine.
* One intent-detection call, a lookup-table router, five agent modules and a refusal path.
* A reproducible dataset: real NASA telemetry, plus synthetic factory, fleet and document data linked to it.
* A portable evaluation set and harness, which project 2 reuses unchanged.
* A command-line tool and a local browser playground for manual testing.

### Out of scope (non-goals)

* Coordinators, fan-out, answer merging, microservices, a gateway, or cloud deployment. These belong to project 2.
* Any real manufacturer's name or internal data. No defense or export-controlled content.
* Real FAA airworthiness directives in the knowledge base. All 10 documents are synthetic.
* Azure safety and red-team evaluators, which need an Azure project.

## 3. Architecture

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

| Component | Location | Responsibility |
|---|---|---|
| Intent detection | `routing/intent.py` | One model call that returns exactly one of `telemetry`, `service`, `production`, `quality`, `knowledge`, `unsupported`. Anything unparseable becomes `unsupported`. |
| Router | `routing/router.py` | `ROUTES` dict from label to `handle()`; `unsupported` has no route and is refused. |
| Pipeline graph | `routing/graph.py` | LangGraph `StateGraph`: intent node, then a conditional edge to one agent node or the refusal node. Times every stage. |
| Agent modules | `agents/<name>/` | Each exposes `handle(question, context) -> AgentReply`. |
| Shared agent code | `agents/common/` | Plain-Python tool loop, the read-only SQL tool, and the `AgentContext` / `AgentReply` / `ToolStep` contract. |
| Model client | `llm/client.py` | OpenAI-compatible chat client. Reports tokens, model time and rate-limit wait separately. |
| Data build | `data/` | Builds the SQLite database, CSVs, knowledge documents and evaluation questions. |
| Evaluation | `evaluation/` | Exact evaluators, Azure AI Evaluation SDK harness, runner and report. |
| Interfaces | `cli.py`, `serving/` | Command line and the local browser playground. |

**The router's limitation is intentional.** Questions that need two agents get a partial answer or a wrong one. That failure is the evidence project 2 exists to address, and it must not be "fixed" in this project.

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
| FR-16 | CLI: `uv run contoso-aero "question" [--json]`. |
| FR-17 | Playground: `uv run contoso-aero-ui` serves `http://127.0.0.1:8010`. |
| FR-18 | The playground offers router mode or a direct call to one agent. It shows the chosen agent, the answer, the per-stage time split (model vs. rate-limit wait), tokens and each tool call with its SQL and output. |
| FR-19 | The playground binds to loopback only, runs one question at a time, limits requests to 4 KB and questions to 1,000 characters, and never returns the API key. |

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

`data/eval/questions.jsonl` holds 59 questions, shared unchanged with project 2.

| Category | Count | Expectation for this baseline |
|---|---:|---|
| Single-agent | 24 | Router should route and answer correctly |
| Multi-agent | 23 | Routing scores 0% by design; answers will mostly fail |
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
| Test set | `data/eval/questions.jsonl` | 59 | Frozen release gate, shared unchanged with project 2 |
| Routing dev set | `data/eval/routing_probe.jsonl` | 19 | Hand-written questions used to tune and check the router |

* Prompts and agents are tuned only against the dev set. The test set is never edited to make a run pass.
* A router fix counts only if the dev probe passes with repeats (`uv run python -m contoso_aero.evaluation.probe --repeat 3`) and the test set does not regress.
* The dev set calls only intent detection, so a probe run costs a few thousand tokens instead of a full evaluation.

### Metrics

**Primary metrics (exact, code-based):**

* routing accuracy
* answer correctness: all expected facts found and all numbers within tolerance
* correct refusals
* latency per stage (intent, agent, total)
* rate-limit wait
* token counts

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
| NF-1 | Latency honesty | Every stage is timed by the project itself, not by framework callbacks. Rate-limit wait is recorded separately from model time, and comparisons with project 2 use model time. |
| NF-2 | Rate limits | 429s are retried using `Retry-After`, up to 8 times. A wait longer than 65 s means the daily quota is used up, so the run fails fast instead of stalling. |
| NF-3 | Security | Keys come from the project's own git-ignored `.env` (`NL_SQL_BASE_URL`, `NL_SQL_API_KEY`, `NL_SQL_MODEL`, optional `NL_SQL_MODEL_TIMEOUT_SECONDS`). Real environment variables override the file. Keys are hidden from `repr` and never committed or logged. |
| NF-4 | Module boundary | Agent modules never import each other. Only the router calls them, through `handle()`. Tests enforce this, so in project 2 extracting a module means only wrapping `handle()` in a service. |
| NF-5 | Framework boundary | LangGraph is used for the router graph only. Agent modules import no LangGraph or LangChain code (enforced by a test). |
| NF-6 | Reproducibility | A fixed seed, a fixed snapshot date, a pinned SDK and a recorded `uv.lock`. |
| NF-7 | Code structure | `src/contoso_aero/` is split into stage sub-packages, one responsibility per file, with public APIs exported from `__init__.py`. Configuration lives in `config.py`. |
| NF-8 | Module guides | Every core module has `guide/<module>.md`: an H1 file name, a one-line summary, then exactly 5 bullets. A test enforces this, and the guides are kept in sync with the code. |
| NF-9 | Tests | `pytest` with a scripted fake model (no network) and given/when/then names. `ruff` with line length 100. Currently 57 tests pass. |
| NF-10 | Repository | This project is its own repository with its own `.venv`, `.env` and `.copilot-tracking/` (git-ignored). It shares nothing with `nl-to-sql`. |

## 8. Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Pattern | Router in a modular monolith, one agent per question | Faithful copy of the client's original system, as the baseline |
| Brand | Contoso Aero Engines | Microsoft's standard fictional company; implies no real manufacturer |
| Telemetry | NASA C-MAPSS FD003 | Real data, 100 engines, two fault modes that support two factory stories |
| Language and tooling | Python 3.11+, `uv`, `pytest`, `ruff` | Matches the sibling `nl-to-sql` project |
| Router framework | LangGraph `StateGraph`, routing only | Clear graph for the router; agents stay portable for project 2 |
| Agent loop | Plain Python | No framework to carry into microservices; full control of timing |
| Storage | SQLite with a read-only authorizer per agent | Simple, local, enforces table ownership |
| Retrieval | BM25 over Markdown documents | Simple and transparent at 10 documents |
| Model | `openai/gpt-oss-120b` via Groq, OpenAI-compatible | Same endpoint as `nl-to-sql`; free tier |
| Evaluation | Azure AI Evaluation SDK, exact checks plus built-in judges | A library-based, production-style harness that matches the Microsoft audience |
| Judge model | Same as the agents | Owner's choice to stay on the free tier; bias disclosed |
| Budget | Stay on the free tier; split evaluation across days | No paid usage |
| Playground | Standard-library HTTP server and one HTML file | No extra dependencies; local only |

## 9. Current status

| Area | Status |
|---|---|
| Dataset, agents, router, CLI | Done |
| Browser playground | Done and tested in the browser |
| Evaluation harness | Done; day 1 complete |
| Day-2 judge run | Pending |
| Results write-up | Pending |
| Routing-gap fix | Planned (Copilot prompt prepared); not yet applied |
| Code review of agents and router | Pending |
| Deployment | None (local only) |

### Day-1 baseline (run `20261030T143443Z`, exact checks, 59 questions, 0 errors)

| Category | Routing | Answers correct | Refusals | Mean total time |
|---|---:|---:|---:|---:|
| Single | 79.2% | 75.0% | n/a | 11.7 s |
| Multi | 0% (by design) | 8.7% | n/a | 20.0 s |
| Unsupported | 100% | n/a | 100% | 1.9 s |
| **All** | 52.5% | 42.6% | 100% | 12.9 s |

* **Most of the measured time is rate-limit waiting.** The mean wait was 9.9 s of the 12.9 s total, against about 3.1 s of model time. 46 of 59 questions waited at least once. All reports must state this.
* **Tokens:** 96,842 in and 23,520 out.

## 10. Known issues

### Single-agent routing gaps (not the intended limit; to be fixed)

The router sees only the question and one line per label. It never sees the tables or documents each agent owns, so it decides from wording.

1. **Missing descriptions.**
   * Telemetry owns the fleet tables, but its description only mentions sensor readings, and the prompt never says that Contoso's customers are airlines.
   * A question that names an airline therefore looks like a question about another company and is refused. "How many active engines operate?" routes correctly. "How many active engines does Northwind Air operate?" is refused. It routes correctly only when it says "in our fleet".
   * Affected: Q004 (refused) and Q003 (sent to service).
2. **Overlapping descriptions.** Questions about what a procedure, limit or term says are routed by their topic words instead:
   * Q021 says "borescope" and goes to service.
   * Q023 says "T50" and goes to telemetry.
   * Q024 says "disposition" and goes to quality.

   All three should go to knowledge.

**Fix plan:**

* Describe each agent by everything it owns.
* State that Contoso's fleet is made of customer airlines.
* Add one general tie-break rule: questions about what a rule, limit or term says go to knowledge.
* Add no question-specific wording, and add a test that rejects eval IDs and airline names in the prompt.
* Check the fix on a held-out set of new probe questions.
* Rerun day 1 as `baseline-exact-v2` and report before/after. Expect unsupported to stay at 100% and multi routing at 0%.

### Q011: data visibility, not routing

The question was routed correctly. The answer said `P1` because the production agent only sees `plant_id`, while the plant names exist only in `data/reference.py` and one knowledge document. The fix is to add the plant names (built from `data/reference.py`) to the production agent's notes.

### Other notes

* The judge model once returned invalid JSON on a refusal row (HTTP 400). That row is excluded from groundedness anyway. Judge runs use `fail_on_evaluator_errors=False`.
* Some ambiguity is inherent. A question like "Has engine X passed the T50 alert limit?" needs both telemetry and knowledge. That is the intended limit, not something a prompt can fix.

## 11. Contract with project 2

Project 2 must reuse, unchanged:

* `data/eval/questions.jsonl` and the scoring rules (evaluators, tolerances, fact normalisation).
* The dataset build (same seed and snapshot date), so answers match.
* The agent modules, wrapped as services through `handle(question, context) -> AgentReply`.
* The same model endpoint and the same rate-limit accounting, so latency compares model time with model time.

Project 2 is expected to improve multi-agent routing and answers, at the cost of extra coordinator latency. That trade-off is what the comparison measures.

## 12. Remaining work

1. Apply the routing-gap fix and the Q011 plant-name fix, then rerun day 1 (`baseline-exact-v2`).
2. Run the day-2 judge sample on a day with a fresh token quota.
3. Write up the baseline results with their caveats: rate-limit-dominated latency, multi-agent failures as expected evidence, and same-model judge bias.
4. Review the agent and router code.
5. Update the README with the headline numbers.
