# Kickoff: Contoso Aero Engines assistant, modular monolith with a router

Use this as the first message to the RPI Agent. Start in manual mode and stop after Research so the findings can be reviewed.

## Why this project exists

This is project 1 of 2, based on the Microsoft ISE article "Orchestration Patterns for Multi-Agent Systems" (Lily Jia, 12 June 2026): <https://devblogs.microsoft.com/ise/coordinator-patterns-multi-agent-systems/>.

The article describes a client whose production chatbot was a **router pattern inside a modular monolith**. A separate intent-detection LLM labelled each query, and a router sent it to **exactly one** agent module. Everything lived in one app, one codebase and one deployment, owned by one central team. ISE later moved them to coordinators over agent microservices, and found the coordinator adds real latency.

This project rebuilds the **original** architecture faithfully, as a measured baseline. Project 2, a separate standalone repo, will rebuild it as coordinators over agent microservices behind a gateway, using the same data and the same evaluation set, so the two can be compared fairly.

The audience is a Microsoft manufacturing and mobility team. The domain is therefore aerospace manufacturing (the factory) linked to aviation operations (engines in service). This is the "digital thread" from factory to fleet.

## What to build

A question-answering assistant for **Contoso Aero Engines**, a fictional jet-engine maker. Contoso is Microsoft's standard fictional company name. Use no real manufacturer's name for anything synthetic.

### Request flow (the client's original pattern)

1. The user asks a question (CLI first).
2. **Intent detection:** one separate LLM call returns exactly one label: `telemetry`, `service`, `production`, `quality`, `knowledge` or `unsupported`.
3. **Router:** a LangGraph `StateGraph` with a conditional edge from the intent node to exactly one agent node. `unsupported` goes to a refusal node without calling any agent.
4. **One agent module** answers, using an LLM with tools over its own data.
5. The answer is returned as-is. There is no merging and no second agent. This limitation is intentional: do not use LangGraph fan-out, parallel branches or a merge node in this project.

### The five agent modules

| Module | Side | Data |
|---|---|---|
| Engine telemetry | Fleet | **Real** NASA C-MAPSS turbofan run-to-failure data (sensor readings per flight cycle). Map each C-MAPSS unit to a fictional Contoso engine serial number (ESN). |
| Service and maintenance | Fleet | Synthetic shop visits, removals and findings, with fields shaped on public FAA Service Difficulty Reports. |
| Production traceability | Factory | Synthetic: ESN → build date, plant, assembly line, module serials (fan, compressor, combustor, turbines), supplier lots. |
| Quality | Factory | Synthetic: inspections, nonconformance reports, deviations, supplier-lot quarantines. |
| Knowledge | Both | Search over synthetic Contoso service bulletins and maintenance procedures, structured like FAA airworthiness directives. Optionally include a small set of real FAA airworthiness directives (Federal Register API) as clearly attributed public reference documents. |

All synthetic data is linked by ESN, supplier lot and date, so a fleet symptom can be traced to the factory. Plant a few deliberate "stories" with known answers. For example: one turbine-blade supplier lot was used during a quality deviation, and engines built with it map to the fastest-degrading C-MAPSS units.

### Evaluation (build it in the first slice, not last)

The article's lesson is "measure early". Build a portable JSONL question set (around 60 questions) that project 2 will reuse unchanged. Each item records the question, the expected agent or agents, the expected key facts, and a category:

* **Single-agent** (about 40%): the router should handle these.
* **Multi-agent** (about 40%): these need two or more agents, for example "Engines showing high turbine temperature: which supplier lot built them, and was there an open deviation?" The router is expected to fail these. That failure is the evidence for project 2.
* **Unsupported** (about 20%): off-topic, abusive, prompt injection and non-language input.

Metrics per run:

* routing accuracy
* answer correctness (expected facts found)
* correct refusals
* latency per stage (intent detection, agent, total)
* token counts

Judgement metrics (LLM judge):

* groundedness (the answer is supported by the agent's tool results)
* relevance
* intent resolution

#### Evaluation harness: Azure AI Evaluation SDK

* Use `azure-ai-evaluation` and its `evaluate()` call as the **single harness**. It reads the JSONL rows, runs every evaluator on each row and produces one results table.
* **Exact checks are custom code evaluators**, not LLM judges: routing accuracy, expected facts found, expected numbers within tolerance, and correct refusals. Write each as a small plain function with its own pytest tests, then register it with `evaluate()`.
* **Built-in evaluators** cover the judgement metrics: `GroundednessEvaluator`, `RelevanceEvaluator` and `IntentResolutionEvaluator`.
* **Judge model:** the same model and endpoint the agents use, passed as an OpenAI-compatible model configuration. A model grading its own answers is biased, so write this in every report and treat judge scores as indicative. The exact checks are the primary results.
* Record judge calls (latency, tokens, retries) **separately** from agent calls, so evaluation cost never pollutes the latency numbers.
* Run locally and write results to files. Logging to an Azure AI Foundry project is optional and must not be required. Leave out safety and red-team evaluators, because they need an Azure project.
* The `ground_truth` table and `data/eval/questions.jsonl` are for the harness only. No agent may read them.
* Pin the SDK version and record it in each run's JSON, because some agent evaluators are still in preview.

Save per-run JSON plus a short Markdown report.

## Constraints

* Python 3.11+, managed with `uv`. Match the conventions of the sibling project `../nl-to-sql` (scripted fake model in tests, `ruff`, `pytest`).
* **LangGraph for routing only.** The graph holds the intent node, the conditional edge, the agent nodes and the refusal node. Each agent node is a thin wrapper that calls the agent's `handle()`. Agent modules themselves import no LangGraph or LangChain code, so project 2 can wrap them as services without the framework. Pin `langgraph` (and `langchain-openai`, if used) in `pyproject.toml`.
* **Time every step yourself** (intent detection, agent, total, retry wait). Do not rely on framework callbacks for the latency numbers.
* Model: the **same OpenAI-compatible endpoint and model that `nl-to-sql` uses**. Read the base URL, API key and model name from this project's own `.env`, using the same values as the `NL_SQL_BASE_URL`, `NL_SQL_API_KEY` and `NL_SQL_MODEL` settings in `../.env`. Never commit keys. The endpoint is rate-limited (`nl-to-sql` retries on HTTP 429), so record retry and wait time **separately** from model time; otherwise the latency numbers are meaningless.
* SQLite for structured data. Keep retrieval for the knowledge agent simple (BM25 or similar) unless Research finds a strong reason otherwise.
* **Module boundary rule:** agent modules never import each other. Only the router calls a module, and only through one public function, `handle(question, context) -> AgentReply`. Add a test that enforces this. Project 2 depends on it: extracting a module must mean wrapping `handle()` in a service, nothing more.
* Layout: `src/<package>/` grouped by stage, for example:
  * `data/`
  * `agents/<one sub-package per agent>/`
  * `routing/`
  * `evaluation/`
  * `serving/`

  Keep `config.py` and `cli.py` at the top level. One responsibility per file. Each sub-package exports its public API from `__init__.py`. Use type hints and docstrings that say why. Keep configuration in one place and set seeds for reproducibility.
* Each sub-package with core modules gets a `guide/` folder with one `<module>.md` per core module: an H1 of the file name, a one-line summary, and exactly 5 bullets. Keep these in sync with the code.
* When adding a top-level folder named like an ignore pattern (for example `data/`), make the ignore patterns root-anchored.

## Non-goals

* No coordinator, no microservices, no gateway, no cloud deployment. Those belong to project 2.
* No real company data presented as a real manufacturer's internal data.
* No defense or export-controlled content.

## Already decided (do not reopen)

* Router pattern in a modular monolith, one agent per query.
* Fictional brand Contoso Aero Engines, with real NASA C-MAPSS telemetry and FAA-shaped synthetic records.
* LangGraph for the router graph only; agent modules stay framework-free.
* The same model endpoint as `nl-to-sql`, for the agents and for the LLM judge.
* Azure AI Evaluation SDK as the evaluation harness, with exact checks as custom code evaluators.
* An evaluation set shared with project 2.

## Ask Research to verify first

1. The current download location, licence and file format of NASA C-MAPSS. Pick which subset or subsets to use.
2. The FAA Service Difficulty Report fields, and the Federal Register API query for airworthiness directives.
3. Which of `nl-to-sql`'s model-client and tracing code to copy rather than rewrite.
4. The current `langgraph` and `azure-ai-evaluation` versions, how `evaluate()` accepts an OpenAI-compatible model configuration (base URL, key, model), and the input fields each chosen built-in evaluator needs.
5. A suggested split of the work into slices, each with its own RPI loop:
   1. data
   2. evaluation set and harness
   3. agent modules
   4. intent detection and router
   5. CLI and report

## Reference material in this folder

* `docs/architecture-monolith-vs-microservices.excalidraw`: architecture only, before and after.
* `docs/client-vs-suggested-architecture.excalidraw`: the article's full story.
