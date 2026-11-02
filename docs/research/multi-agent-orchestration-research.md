<!-- markdownlint-disable-file -->
# Task Research: multi-agent-orchestration

| Field              | Value         |
|--------------------|---------------|
| Date               | 2026-10-29    |
| Researcher / agent | rpi-research  |
| Output mode        | research-only |

## Executive Summary

* Bottom line: The project’s architectural baseline, sibling reuse patterns, FAA field shapes, and a bounded five-slice RPI sequence are now grounded. The first implementation gate is blocked on the requested NASA C-MAPSS asset: NASA’s current catalog marks downloads unavailable, and no dataset-specific license, file format, or subset was verified.
* Why this matters: Starting from a third-party copy or assuming the paper’s use statement covers the dataset could undermine provenance and the project’s stated real-data requirement. Federal Register results also need document-type/effectiveness checks before being treated as current directives.
* Research status: Completed for the available evidence; partially resolved for Q1 and Q2 because the official NASA asset terms/format/subset and current FAA/API contracts remain unverified.
* Confidence and uncertainty: High confidence in the retrieved NASA notice, FAA form labels, sample API response, ISE article, and sibling code behavior. Missing facts remain explicitly unresolved rather than being inferred.

## What You May Not Know

The C-MAPSS catalog entry and the NASA PHM08 paper refer to related simulator outputs but do not establish that the current catalog record is the classic FD001–FD004 run-to-failure package. Also, the FAA form copy retrieved from its official domain prints an OMB expiration date in 2020. Treat the FAA fields as synthetic shape only, not current compliance guidance. The ISE article’s original client was an anonymized retail organization; Contoso Aero Engines is the project’s fictional manufacturing adaptation, not a reproduction of that customer.

## Findings

### The sibling provides reusable client and test patterns, not ready-made stage metrics

`nl-to-sql` has a standard-library Chat Completions client with injectable transport and wait functions, bounded HTTP 429 retries, and response token counts. Its task runner records end-to-end task duration, while the JSONL tracer records ordered, timestamped message/tool events and redacts common credential forms. These are useful implementation patterns for the new project; the current behavior does not itself separate intent-detection time, agent time, and retry wait, so those measurements must be explicitly designed and tested if the comparison requires them.

* Questions: Q3
* Evidence state: Evidence-backed finding
* Evidence: C3, C4
* Confidence and limits: High for the inspected client, tracer, task-runner, and tests. The sibling’s SQL-specific settings and agent are not directly reusable as a domain module; no claim is made that every package should be copied unchanged.

### NASA currently marks its C-MAPSS download unavailable; the data rights and subset remain unresolved

NASA’s current data-catalog entry says C-MAPSS and C-MAPSS40K are unavailable for download while availability requirements are reviewed. The catalog describes simulated engine/flight measurements at 1 Hz with 30 parameters, while NASA’s 2008 paper record describes cycle-indexed sensor time series used as PHM08 challenge data. The paper record says “Public Use Permitted” for the paper; it does not establish a license for redistributing the underlying dataset. Therefore the official current source does not yet support the brief’s assumed download path, exact file format, or FD001–FD004 subset choice.

* Questions: Q1
* Evidence state: Evidence-backed finding
* Evidence: W1, W2
* Confidence and limits: High that NASA’s current catalog page contains an unavailability notice and high that the NASA paper discusses cycle-series challenge data. Dataset-specific permission, downloadable bytes, and exact relationship between the portal record and classic FD001–FD004 files remain unresolved.

### FAA fields and the Federal Register API are useful starting points, with currency checks required

The retrieved FAA Form 8070-1 provides concrete, public field shapes for equipment identity, event date, problem description, part condition/location, service time, installed component, and submitter type. A real Federal Register API request filtered by the phrase “airworthiness directive” and FAA agency returned recent documents, but the results included both `Proposed Rule` and `Rule`. A consumer should therefore verify the document’s final/effective status and applicability rather than treating every text match as an operative directive.

* Questions: Q2
* Evidence state: Evidence-backed finding
* Evidence: W3, W5
* Confidence and limits: High that the request worked and returned the observed types, and high for the form’s printed labels. The API documentation endpoint was access-gated, and the retrieved form’s printed OMB date is expired, so current query options and current reporting requirements are not established.

### The requested work separates naturally into five RPI slices, with evaluation started in slice one

The brief’s order follows the dependency shape: establish stable data/story facts, exercise domain modules against a reusable evaluation contract, then add single-agent routing, and finally deliver CLI/report integration. To honor “measure early,” create the evaluation JSONL schema and first question set in the data slice; build the full harness in the next slice, before agent implementation. Keep each slice’s RPI loop bounded by observable contract/tests rather than by a broad feature label.

* Questions: Q4
* Evidence state: Evidence-backed finding
* Evidence: C1, C3, C4, W4, W6, W7
* Confidence and limits: High for explicit requirements and the dependency from module contracts to router/CLI. The split is a research proposal, not an approved plan; it assumes the NASA source gate is resolved before importing real telemetry.

## Recommendation and Alternatives

* Recommendation or decision state: Preserve the caller’s architecture decisions. Candidate slice order below responds to Q4; it is not a plan or authorization to implement. Keep the NASA source gate unresolved until the user chooses the next evidence path.
* Rationale: C1 and W4 confirm the required baseline pattern; C3-C4 support reusing the HTTP/retry/test patterns but not assuming their timings meet this comparison; W1-W2 leave the real-data source uncleared.
* What could change this result: NASA restoring an attributable download with terms; an explicitly authorized mirror whose files and data rights are separately verified; or a change to the caller’s confirmed data requirement.

| Candidate RPI slice | Bounded outcome and exit evidence | Dependency or risk | Evidence | Disposition |
|---------------------|-------------------------------|---------------------|----------|-------------|
| 1. Data foundation and evaluation contract | Clear the NASA acquisition/terms gate; define SQLite entities and deterministic synthetic story/link keys; write the JSONL evaluation schema and initial questions. | Do not ingest a mirror or imply real manufacturer provenance without verified asset rights; user wants the evaluation built early. | C1, W1, W2, W5, W7 | Proposed |
| 2. Evaluation corpus and harness | Complete the portable ~60-question set (about 40% single-agent, 40% multi-agent, 20% unsupported), scripted model path, scoring for facts/refusals/routing, and per-run JSON; test on the fixed fixture before modules. | Freeze expected facts against the seeded story and keep the evaluation data reusable by project 2; multi-agent cases are expected to expose this router baseline’s limitation. | C1, C3, C4, W6 | Proposed |
| 3. Agent modules | Implement/test each module’s single `handle(question, context) -> AgentReply` contract against its own data. | Must preserve the no-cross-import rule; module tests need deterministic data and fake model replies. | C1, C3, W6 | Proposed |
| 4. Intent detection and router | Validate one exact label, route to exactly one `handle`, and return `unsupported` safely without invoking an agent; add an import-boundary test. | Must not merge answers or call a second agent; multi-agent evaluation cases should expose the expected baseline limitation. | C1, W4 | Proposed |
| 5. CLI and report | Run the complete flow and write per-run JSON plus a short Markdown report with per-stage latency, retry/wait separated from model time, and tokens. | Depends on stable evaluation outputs and stage instrumentation; end-to-end duration alone is insufficient. | C1, C3, C4 | Proposed |
| Delay real telemetry ingestion pending a cleared source | Preserves the real-data requirement and provenance. | Blocks the real telemetry path until NASA access/terms or a verified same-dataset mirror are available. | W1, W2 | Current gate |
| Use a third-party mirror immediately | Could unblock early local data work. | Search results show repositories but no verified data-specific rights or exact file provenance; repository code license does not establish a license for bundled data. | W1, W2, W8 | Not cleared; user authorization and evidence required |

## Scope and Questions

* Goal: Verify the kickoff brief's key external data sources, reuse candidates from the sibling `nl-to-sql` project, and identify evidence-backed research slices.
* Audience and use: The project owner and a future manual RPI planning session for the Contoso Aero Engines modular-monolith baseline.
* In scope: NASA C-MAPSS provenance, licensing and format; FAA Service Difficulty Report fields and Federal Register API query approach; sibling model-client and tracing code; and slice boundaries for data, evaluation, agent modules, routing, and CLI/reporting.
* Out of scope: Source changes, implementation, plan creation, real manufacturer data, credential handling, project 2 architecture, and any cloud or multi-agent-framework design.
* Decision and evidence criteria: Prefer authoritative NASA, FAA, Federal Register, Microsoft, and repository sources; verify exact formats, interfaces, licensing, and behavior; distinguish facts from design implications.
* Requested output: Research-only synthesis with verified findings, alternatives, remaining questions, and a suggested slice breakdown; no handoff beyond this Research phase.

| ID | Question | Source | Status |
|----|----------|--------|--------|
| Q1 | Where is NASA C-MAPSS currently obtained, what are its usage/licensing terms and file format, and which subset is appropriate to evaluate? | User brief | Partially answered; NASA catalog says unavailable; exact classic asset/terms/format/subset unresolved |
| Q2 | Which FAA Service Difficulty Reporting fields can shape synthetic records, and how should the Federal Register API be queried for airworthiness directives? | User brief | Partially answered; form fields and a sample query verified; current form status/API documentation unresolved |
| Q3 | Which sibling `nl-to-sql` model-client and tracing components should be reused rather than rewritten? | User brief | Answered; see C3-C4 |
| Q4 | What evidence-backed project slices fit the requested order and can be run as separate RPI loops? | User brief | Answered with a candidate five-slice sequence; user approval remains |

## Decisions and Feedback

| Group | Decision or feedback item | Status | Owner | Rationale or input needed | Evidence | Impact of answer |
|-------|---------------------------|--------|-------|---------------------------|----------|------------------|
| D1 | Begin with the supplied research scope, manual/user-owned participation, and stop after Research. | Confirmed | User | The kickoff prompt explicitly directs a manual start and a Research-only stop. No intake question is needed to begin. | User brief | No automatic planning or implementation transition. |
| D2 | Choose the next evidence path for the real C-MAPSS asset: wait on NASA, or authorize bounded research into an exact third-party copy while retaining provenance and license gates. | Unresolved; input requested | User | NASA’s official catalog currently says downloads are unavailable and the paper’s permission does not establish dataset rights. | W1, W2 | Determines whether the data slice can clear its real-telemetry gate or remains blocked. |

## Risks and Open Questions

| Priority | Type | Risk, question, or research item | Impact | Smallest action or evidence needed | Owner |
|----------|------|----------------------------------|--------|------------------------------------|-------|
| High | Blocker | NASA’s current catalog marks C-MAPSS and C-MAPSS40K unavailable for download; dataset-specific license and classic subset format were not verified. | Blocks selecting a cleared real telemetry asset and may force a user decision about an alternative source or deferred download. | Obtain a NASA-restored download and dataset-specific terms, or have the user authorize a separately verified source/alternative. | User / research |
| Medium | Risk | Sample Federal Register query results contain both proposed and final rules. | A text search alone can lead to treating a proposal as an operative airworthiness directive. | Confirm supported type/effectiveness filters from documentation or verify each selected document’s official status and effective date. | Research |
| Medium | Risk | FAA Form 8070-1 retrieved from the FAA site shows an expired OMB date. | The synthetic schema could incorrectly imply current required reporting fields. | Confirm the current approved form or explicitly label fields as historical/public shape rather than compliance requirements. | Research / user |
| Medium | Risk | Existing task-level duration and retry handling do not establish the stage-level latency measurements required by this project. | A baseline comparison could misattribute throttling wait to model time. | Retain separate intent, model-call, retry-wait, agent, and total measurements in the evaluation contract. | Downstream |

## Planning Readiness and Next Step

| Field | Record |
|-------|--------|
| Research disposition | executed |
| Decision participation | user-owned; manual mode explicitly requested |
| Planning Readiness | Not applicable during research-only mode; the requested phase gate is to stop after Research. |
| Research depth and helpers | Cycle 1 Wider, Deeper, and Contrarian completed; no helpers dispatched. |
| Blockers | NASA dataset download and dataset-specific terms are unresolved (W1-W2). |
| Output mode and planning support | research-only; does not initiate a planning handoff. |
| Continuation owner | Manual RPI Agent / user |
| Required gates or confirmations | Research cycle and synthesis complete. Wait for user direction on NASA source discovery; no automatic plan transition. |
| Next action | Choose whether to wait for NASA restoration or authorize a bounded verification of an exact third-party copy. Do not start implementation or planning until explicitly advanced. |
| Primary evidence file | .copilot-tracking/research/2026-10-29/multi-agent-orchestration-research.md; date from the supplied current date. |

## Research Record

### Method and Boundaries

| Field | Record |
|-------|--------|
| Research posture and provenance | balanced; default from rpi-research |
| Helper lane effort | auto; no helpers selected |
| Completion basis | Cover the four caller questions, verify material claims from primary sources and repository code, complete all three waves, and stop after synthesis. |
| Explicit limits or deadline | Caller says start in manual mode and stop after Research; no other deadline. |
| Codebase and external scope | Workspace: multi-agent-orchestration docs and nl-to-sql source/tests/config. External: NASA C-MAPSS, FAA SDR, Federal Register API, and the named Microsoft ISE article. |
| Initial candidate areas | Internal: multi-agent-orchestration/docs/copilot-initial-prompt.md; nl-to-sql/README.md; nl-to-sql/src/nl_sql/agent/model_client.py; nl-to-sql/src/nl_sql/agent/tracing.py; nl-to-sql/src/nl_sql/config.py; corresponding tests and project metadata. External: authoritative NASA, FAA, Federal Register, and Microsoft sources. |
| Evidence root | Repository root .copilot-tracking/; default dated research path. |
| Constraints and excluded sources | Research-only; do not edit project/source files or expose credentials. No `.env` files were read. Use only fictional Contoso data for synthetic examples. Do not expand into project 2 or architecture implementation. |
| Prior knowledge | The user-supplied kickoff document was read as the controlling brief, not as verified evidence. The workspace contains three named Excalidraw diagrams and the kickoff prompt. Sibling client, tracing, configuration, task-runner, evaluation-report, and test contracts were inspected and recorded in C2-C4. |

### Extensions and Participation

#### Extension Registry

| Kind | Candidate | Provenance and scoped contract | Selected or skipped reason |
|------|-----------|--------------------------------|----------------------------|
| Skill | rpi-research | Invoked for the requested Research phase; owns research-only workflow, evidence, and artifact. | Selected; primary workflow contract. |
| Instruction | copilot-tracking-location.instructions.md | Applies to `.copilot-tracking/**`; resolves tracking root to codebase root. | Selected; controls artifact location. |
| Instruction | copilot-tracking.instructions.md | Applies to the research artifact and defines its path and content conventions. | Selected; controls evidence storage. |
| Skill | dataops | Research reference pack for data pipeline and data-science testing context. | Selected for Q4 only; scoped guidance, not authority to generate data or code. |
| Skill | telemetry-foundations | Scoped vocabulary for measurement concepts because the brief requires stage latency and token metrics; SDK/backend choice is out of scope. | Selected for Q3/Q4 measurement boundaries; no new metric or span names are prescribed in this research. |
| Skill | python-foundational | Python coding conventions. | Skipped; this phase does not author Python. |
| Skill | data-catalog | Durable data catalog authoring. | Skipped; user asks for source research and slice framing, not a catalog artifact. |

#### Direction and Participation Log

| Checkpoint or change | Question, direction, or rationale | Answer or no-interaction reason | Result and revalidation effect |
|----------------------|-----------------------------------|---------------------------------|--------------------------------|
| Intake | Does the user need to choose scope, output mode, or priorities before research? | No; the kickoff prompt names four research questions, expected audience, constraints, and an explicit manual Research-only stop. | Proceed with research-only output and user-owned decisions; no intake question. |

### Research Cycle Log

#### Cycle 1

* Active posture, controls, and limits: Balanced; answer Q1-Q4; do not implement, plan, or continue beyond Research.

##### Wave 1: Wider

* Focus and questions: Establish candidate official sources for Q1-Q2; inspect sibling project contracts and tests for Q3; use the brief and scoped DataOps guidance to frame Q4.
* Evidence: C1-C4 establish the controlling brief and sibling patterns. W1 shows the NASA catalog’s explicit current unavailability notice; W2 is the NASA paper record and full text. W3 is a successful official Federal Register API query filtered by term and FAA agency. W4 verifies the ISE article title/date and the original router architecture. W5 contains FAA Form 8070-1 field labels and its expired OMB date. Q4 slice dependencies remain under investigation. Direct API documentation and FAA SDR page fetches failed, so those failures are not treated as source facts.
* Reflection: Q3 has concrete implementation evidence. Q1 now has a material acquisition blocker; exact classic subset format and terms must not be inferred from a paper permission or third-party mirror. Q2's form can shape synthetic fields but is not current compliance authority; the query works but official API parameters still need documentation. Continue with API response detail, code-path timing, and slice dependency checks.

##### Wave 2: Deeper

* Focus and questions: Verify exact download/license/format and subset trade-offs; query fields/parameters and reproducibility; trace model-client and timing behavior to code/tests; map dependencies and testable slice outputs.
* Evidence: W1-W5 verify NASA’s download notice and paper, sample Federal Register query, article context, and FAA form fields; C3-C4 establish sibling client/tracing behavior. Remaining internal code-path details and exact subset comparison are pending.
* Reflection: NASA’s catalog description and PHM08 paper point to related but not yet reconciled representations; do not identify their file formats as equivalent. The retrieved FAA form prints an expired OMB date. The exact API contract and slice dependencies still need deeper verification.

##### Wave 3: Contrarian

* Focus and questions: Seek counter-evidence on dataset subset suitability, alternate official reporting fields/API retrieval choices, reuse-versus-rewrite risks, and slice dependency/order assumptions.
* Evidence: W1 and W2 do not reconcile the current catalog’s 1-Hz/30-parameter flight description with the older PHM08 cycle-series paper, and neither verifies classic FD001–FD004 files or dataset rights. W3’s working query returns both proposed and final rules. W5’s form copy has the expired OMB date. W8 identifies public repository candidates but provides repository-level licensing only. C3-C4 show retry wait is inside client execution while task duration is end-to-end; this challenges a “copy as-is” approach. W6-W7 support test-first modularity and separating transforms from data access, not a particular product slice order.
* Reflection: Counter-evidence strengthens the decision to keep the NASA asset and FAA compliance interpretations gated. No counter-evidence changes the caller’s confirmed modular-monolith/router behavior. Evaluation should start early, but its fixed expected facts depend on the deterministic data/story contract; include the schema and seed questions in slice 1, then finish the harness in slice 2 before agents. The sibling client is a pattern source, not a direct import.

##### Synthesis and Re-entry

| Material or claim | Evidence | Disposition | Rationale | User-facing effect |
|-------------------|----------|-------------|-----------|--------------------|
| Reuse candidate: client, retries, token usage, tracing, scripted tests | C3, C4 | Accepted as patterns; exact adoption deferred | Existing code offers a close starting point, but the new app needs stage and retry-wait measurements. | Answer Q3; retain separate latency measurement as a requirement for Q4. |
| NASA C-MAPSS access and rights | W1, W2, W8 | Deferred | NASA currently marks download unavailable; the paper’s rights do not establish dataset rights; third-party repository metadata does not establish data rights. | Q1 remains partially unresolved and blocks clearing the real telemetry asset. |
| Treating paper permission as dataset permission | W2 | Rejected as unsupported | NASA’s record grants public use for the paper; it does not assert rights for the underlying data. | Do not use this as a dataset license or distribution grant. |
| FAA SDR field shape and directive retrieval | W3, W5 | Accepted as synthetic shape and query prototype; current compliance use deferred | Form fields are concrete, but its OMB date expired; API sample includes proposed rules. | Answer Q2 with explicit validation caveats. |
| Early evaluation and slice sequence | C1, C3, C4, W4, W6, W7 | Proposed | User’s evaluation-first requirement and dependency boundaries support schema/questions in slice 1 and harness before modules. | Answer Q4 with a five-slice candidate map. |

* Another complete three-wave cycle needed: No.
* Trigger or stop basis: All four questions have either an evidence-backed answer or the smallest unresolved gap; source claims are grounded in NASA, FAA, Federal Register, Microsoft, and sibling code. Further progress on Q1 requires user direction about waiting for NASA or authorizing exact-mirror verification; Q2's API-doc access gap does not prevent a bounded query recommendation.
* Readiness or revalidation effect: Research complete under the explicit stop-after-Research boundary. Q1 remains a data-source blocker, and manual mode waits for user direction; no planning or implementation handoff was made.

### Evidence Log

| ID | Claim or finding | Source or location | Retrieved and version | Tool | Confidence | Notes |
|----|------------------|-------------------|-----------------------|------|------------|-------|
| C1 | Workspace scope and kickoff requirements are supplied in the project brief. | multi-agent-orchestration/docs/copilot-initial-prompt.md | not applicable | read | high | Treated as caller direction, not external fact. |
| C2 | Sibling project source and tests are present for review. | nl-to-sql/ | not applicable | filesystem listing | high | File contents assessed in C3-C4. |
| C3 | Sibling client exposes a narrow completion/result contract, injectable transport and wait function, bounded HTTP 429 retries, `Retry-After` handling, and optional usage counts. | nl-to-sql/src/nl_sql/agent/model_client.py; nl-to-sql/src/nl_sql/agent/sql_agent.py | not applicable | read/search | high | Client waits inside the request path; it does not expose a distinct retry-wait duration in the observed result contract. |
| C4 | Sibling tracer appends ordered timestamped JSONL message/tool events and redacts common credential patterns; task-runner results include duration and input/output tokens, with scripted client tests. | nl-to-sql/src/nl_sql/agent/tracing.py; nl-to-sql/src/nl_sql/evaluation/task_runner.py; nl-to-sql/tests/test_model.py; nl-to-sql/tests/test_tracing.py | not applicable | read/search | high | Tracer event timestamps do not by themselves distinguish model time from retry wait or route stages. |
| W1 | NASA's current C-MAPSS catalog entry says C-MAPSS and C-MAPSS40K are currently unavailable for download; it describes simulated 1 Hz flight data with 30 parameters. | NASA Data Catalog, https://data.nasa.gov/dataset/c-mapss-aircraft-engine-simulator-data | 2026-10-29; page state current on retrieval | web_fetch | high | The catalog page was retrieved successfully once; a later fetch failed at transport. No dataset-specific license was established. |
| W2 | NASA’s 2008 paper describes time-series sensed measurements over cycles used as PHM08 challenge data; its NTRS record marks the paper “Public Use Permitted.” | NASA NTRS, “Damage Propagation Modeling for Aircraft Engine Prognostics,” https://ntrs.nasa.gov/citations/20090029214 and https://ntrs.nasa.gov/api/citations/20090029214/downloads/20090029214.txt | 2026-10-29; publication 2008-10-08 | web_fetch | high | Permission applies to the paper record, not automatically to the dataset. |
| W3 | Federal Register API accepted `conditions[term]`, `conditions[agencies][]`, `per_page`, and `order=newest` in an actual FAA airworthiness-directive query. | Federal Register API sample, https://www.federalregister.gov/api/v1/documents.json?conditions%5Bterm%5D=airworthiness%20directive&conditions%5Bagencies%5D%5B%5D=federal-aviation-administration&per_page=1&order=newest | 2026-10-29; API response | web_fetch | high | Returned a 2026-10-28 Proposed Rule and a 2026-10-27 Rule among the newest matches; API docs page was access-gated. |
| W4 | The Microsoft ISE article identifies the original system as a modular-monolith router with separate intent detection and exactly one agent per request, without multi-agent response synthesis. | Microsoft ISE, “Orchestration Patterns for Multi-Agent Systems: Performance and Trade-offs,” https://devblogs.microsoft.com/ise/coordinator-patterns-multi-agent-systems/ | 2026-10-29; published 2026-06-12 | web_fetch | high | This confirms the article's source architecture, not details of the fictional Contoso implementation. |
| W5 | FAA Form 8070-1 identifies aircraft/powerplant/propeller make-model-serial, registration, date, problem description, part name/number/condition/location, part total time and time since overhaul, installed component identity, and submitter category. | FAA Form 8070-1, https://www.faa.gov/documentLibrary/media/Form/FAA_Form_8070-1.pdf | 2026-10-29; PDF marked OMB No. 2120-0663 Exp. 10/31/2020 and form 11-84 | web_fetch + PDFKit text extraction | high | The form is historical evidence for field shape; current OMB approval and current reporting instructions remain unresolved. |
| W6 | Microsoft CSE testing guidance supports test design before implementation, scripted/mocked I/O boundaries, small deterministic fixtures, and separate tests for transformation properties. | Microsoft CSE, “Testing Data Science and MLOps Code,” https://microsoft.github.io/code-with-engineering-playbook/ml-and-ai-projects/testing-data-science-and-mlops-code/ | 2026-10-29; page version not stated | web_fetch | high | Used only to support early evaluation and test-boundary guidance; not a prescribed project architecture. |
| W7 | Microsoft CSE data guidance says to separate data transformation from data access to enable testable transformations and keep replay/idempotency in mind. | Microsoft CSE, “Data and DataOps Fundamentals,” https://microsoft.github.io/code-with-engineering-playbook/design/design-patterns/data-heavy-design-guidance/ | 2026-10-29; last update 2024-08-26 | web_fetch | high | Applied narrowly to transformation/test boundaries; its data-lake tier model is not imposed on this SQLite project. |
| W8 | GitHub repository search surfaced C-MAPSS-labelled repositories, including one whose repository metadata reports GPL-3.0 and several with no license; it did not establish data-specific permission. | GitHub repository search API, https://api.github.com/search/repositories?q=CMAPSS+dataset&per_page=10 | 2026-10-29; search response | gh api | medium | Search results are candidates, not a verified mirror or license for bundled data. No repository contents were downloaded. |

#### Contradictions and Conflicts

* NASA Data Catalog W1 describes 1-Hz flight records with 30 parameters, while NASA NTRS W2 describes cycle-indexed sensed measurements used for PHM08. These may be related C-MAPSS outputs, but the evidence does not establish that the current catalog entry is the classic FD001–FD004 package; resolve with a current NASA data manifest/download and its terms before selecting files.

### Artifact Self-Check

* [x] User-facing findings and continuation are synthesized.
* [x] Every question is answered or names the smallest missing evidence.
* [x] Findings include evidence state, confidence basis, and counter-evidence.
* [x] External evidence has source title, URL, retrieval date, and version where available.
* [x] Cycle includes Wider, Deeper, and Contrarian waves and a re-entry decision.
* [x] Method, extensions, participation, evidence root, boundaries, and prior knowledge are recorded.
* [x] Research-only mode does not force an implementation recommendation or planning handoff.
* [x] Research disposition, readiness, blockers, gates, continuation owner, and next action are complete.
* [x] No secrets or source changes were introduced.
* Checked sections: user-facing summary, all questions, alternatives, decisions, risks, readiness, extensions, participation, all three waves, evidence IDs, and research-only stop.
* Missing or limited sections: Q1 data-specific license, classic file format, and subset remain unresolved; Q2 current FAA form validity and full API parameter documentation remain unresolved. These limitations are recorded as blockers/risks, not treated as findings.
