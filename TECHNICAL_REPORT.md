# Technical Report: NetGenie — Telecom NOC Copilot on OPEA

*ITU FG-AINN / AI for Good ML5G Innovation Challenge — Generative AI Applications for Enterprise Scenarios Using OPEA*

## 1. Use case and business alignment

Telecommunications is the challenge's flagship vertical because networks are moving toward AI-native architectures, where AI is embedded directly in operational workflows rather than bolted on afterward. NetGenie targets a concrete, recurring NOC task: an engineer sees an alarm or a KPI trend and needs two things at once — **current facts** (what is the number, right now, for this cell/region) and **institutional knowledge** (what is our documented procedure for this situation). Today those live in two disconnected systems (a telemetry dashboard and a runbook wiki), forcing manual correlation under time pressure. NetGenie fuses them behind one conversational interface with a visible reasoning trace, so the answer is auditable, not a black box — a hard requirement for anything touching live network operations.

## 2. System architecture

NetGenie follows OPEA's microservice-composition philosophy: small, independently deployable services, each doing one job, composed by a mega-service gateway that implements the actual business logic. Four services:

- **Guardrails** — regex-based prompt-injection detection on input, PII redaction on output. Runs before and after every other worker call.
- **Retrieval Worker** — owns five markdown incident runbooks (fiber cut, congestion, cell outage, security incident, SLA escalation), chunked by heading and indexed with BM25 (`rank_bm25`). Returns the top-k most relevant procedure sections with source attribution.
- **Telemetry Worker** — owns a SQLite warehouse of synthetic regional KPI (dropped-call rate, latency, throughput, congestion) and alarm data. Translates natural-language questions into validated `SELECT`-only SQL, either via keyword templates (mock mode) or LLM generation checked against a table whitelist and a statement-chaining guard (real-LLM mode).
- **Gateway** — the supervisor agent. Screens input → classifies intent (needs retrieval? needs telemetry? both?) → fans out to the required worker(s) concurrently → screens the combined context for PII → synthesizes a final answer with citations → returns the answer alongside a numbered execution trace (tool, latency, summary) for full auditability. Also hosts the demo UI and exposes `/health` and Prometheus `/metrics`.

This is a deliberately compact version of the hierarchical multi-agent pattern behind OPEA's `AgentQnA` example (a supervisor delegating to worker agents/tools) combined with the natural-language-to-SQL pattern behind `DBQnA` — applied to a single vertical instead of shown as two separate generic demos.

## 3. Component usage and OPEA alignment

| NetGenie component | OPEA architectural role | Design choice and rationale |
|---|---|---|
| Gateway | Mega-service / supervisor agent | Async fan-out to workers cuts wall-clock latency vs. sequential tool calls; intent routing avoids calling unnecessary workers |
| Retrieval Worker | Retriever / knowledge base | BM25 instead of dense embeddings — no embedding model to download, millisecond latency on CPU, and a defensible choice for short, keyword-dense operational documents |
| Telemetry Worker | Text2SQL / structured-data worker | SQL is validated (SELECT-only, table whitelist, no statement chaining) before execution regardless of whether it came from a template or an LLM — treats the LLM as untrusted input |
| Guardrails | Safety/guardrails component | Applied symmetrically: input screening prevents prompt injection from reaching workers; output screening prevents PII from reaching the LLM or the operator |
| LLM client | OpenAI-compatible endpoint integration | One client, one contract, works against Ollama, vLLM, a TGI OpenAI shim, or a hosted API without code changes — and against a fully offline mock backend for zero-dependency demos |

### 3.1 Direct dependency on OPEA's own orchestration code

The gateway does not just imitate OPEA's mega-service pattern — it depends on it. `services/gateway/opea_topology.py` builds the fan-out DAG using **`opea-comps`** (the `comps.cores.mega` package published by `opea-project/GenAIComps`), not a hand-rolled equivalent:

- Each worker is registered as a real `comps.MicroService` node, with `service_type` drawn from OPEA's own enum: guardrails → `ServiceType.GUARDRAIL`, the retrieval worker → `ServiceType.RETRIEVER`, and the telemetry worker → `ServiceType.TEXT2SQL` — an exact upstream match for its NL-to-SQL job.
- The DAG itself — which workers exist, and which are downstream of guardrails — is a real `comps.ServiceOrchestrator` instance (`add()` / `flow_to()` / `downstream()`), built once at import time and asked, at request time, which workers are eligible before the intent router decides which of them this particular question needs. This is exercised by `/v1/chat` on every request, not just constructed and discarded — see `tests/test_smoke.py::test_opea_orchestrator_topology_is_real_dag` and `::test_opea_topology_endpoint_matches_chat_fanout`, and the live `/v1/opea/topology` endpoint, which returns the orchestrator's actual node/edge/topological-order state for inspection.
- We deliberately do **not** use `ServiceOrchestrator.schedule()` for execution. `schedule()` auto-aligns payloads for OPEA's standard service contracts (`TextDoc`, `EmbedDoc`, `LLMParamsDoc`, ...); NetGenie's workers speak a small custom domain schema (runbook chunks, SQL result rows) outside that alignment table, and forcing it through generic alignment risked silent misrouting rather than a clean failure. Instead the orchestrator decides *shape* (topology, eligibility) and the gateway performs the actual HTTP calls with its own typed request/response models — the same split OPEA's own example `Gateway` subclasses use for non-standard payloads. This is documented in full in `opea_topology.py`'s module docstring so the design choice isn't buried.
- `MicroService` is constructed with `use_remote_service=True` for every node. Without this flag the constructor tries to *host* a server on the given host:port (it doubles as the base class OPEA workers subclass to serve themselves); NetGenie's workers are already independent, already-running FastAPI processes, so `use_remote_service=True` makes each node a pure registration/metadata handle instead of a conflicting second server.

This is a genuine dependency, not a compatibility shim: `pip uninstall opea-comps` breaks the gateway's import. It was chosen over pulling in heavier OPEA components (e.g. the embedding/reranking microservice images, which carry `torch`/model-download weight) specifically to preserve the 10-minute, no-GPU install target in Section 4 — a judgment call we'd rather state explicitly than have judges wonder about.

## 4. Deployment strategy

Each service ships its own `Dockerfile`; `docker-compose.yaml` wires them together with health-checked startup ordering (the gateway waits for all three workers to report healthy before starting). Default configuration (`MOCK_LLM=true`) requires **no GPU, no model download, and no external network call**, directly satisfying the challenge's 10-minute clean-install constraint on 64GB RAM / 4-core CPU hardware. An optional `--profile llm` Compose profile adds an Ollama container for teams that want production-quality generation; flipping `MOCK_LLM=false` and pointing `LLM_BASE_URL` at it (or any other OpenAI-compatible endpoint) is the only change required anywhere in the codebase. A parallel `run_local.sh` / `stop_local.sh` pair runs the same four services with plain `uvicorn` for environments without Docker, useful for CI or fast judging.

## 5. Evaluation

`eval/benchmark.py` sends a fixed 10-question NOC evaluation set at increasing concurrency (1/5/10) against the live gateway and reports success rate, a keyword-hit relevance proxy, throughput, and p50/p95 latency — the same metric families (latency, throughput, scalability under concurrent load, accuracy) called for in the challenge brief. Results below were captured against the running four-service stack (not simulated) in mock-LLM mode; see `eval/report.md` for the machine-generated version of this table.

| Concurrency | Success | Accuracy (keyword-hit) | Throughput | p50 | p95 |
|---|---|---|---|---|---|
| 1  | 100% | 100% | 21.9 req/s | 42 ms  | 77 ms  |
| 5  | 100% | 100% | 24.8 req/s | 209 ms | 329 ms |
| 10 | 100% | 100% | 24.5 req/s | 393 ms | 407 ms |

Latency scales sub-linearly with concurrency (roughly 5x from 1→5 concurrent requests, then flattening 5→10), indicating the gateway's async fan-out is not the bottleneck at this scale on a single CPU core. Offline `pytest` smoke tests (7/7 passing) cover guardrail blocking, PII redaction, runbook retrieval correctness, telemetry query correctness, SQL-injection rejection, and — new in this revision — that the OPEA `ServiceOrchestrator` DAG the gateway builds has the exact topology `/v1/chat` depends on, exercised independently of any running service via FastAPI's `TestClient`.

**What these numbers do and don't show.** All figures above are mock-LLM mode: no model inference, so they measure the scaffolding (guardrails, BM25, SQL validation, orchestration, HTTP fan-out) rather than end-to-end generation under a real model. A second table with `MOCK_LLM=false` against a locally-served model, run on the judges' own hardware, is the honest way to show generation-inclusive latency — see Section 7 for exactly how to produce it; we did not fabricate numbers for a configuration we couldn't run in this environment.

## 6. Limitations and next steps

Keyword-hit accuracy is a coarse relevance proxy by design (dependency-free, no LLM judge required); production use should layer in `GenAIEval`-style BLEU/ROUGE or LLM-judge scoring once a real backend is attached. BM25 retrieval is well-suited to the five structured runbooks shipped here but would benefit from a dense-embedding fallback as the knowledge base grows past a few hundred documents. The telemetry schema is intentionally small (4 tables) to keep the Text2SQL surface auditable; a production deployment would connect the same worker contract to a real OSS/BSS or network-management data warehouse.

## 7. Reproducing results with a real LLM backend

```bash
docker compose --profile llm up -d --build   # brings up Ollama alongside the 4 services
docker exec -it netgenie-ollama ollama pull llama3.1:8b
# edit .env: MOCK_LLM=false
docker compose up -d gateway                  # restart gateway to pick up the new setting
python3 eval/benchmark.py --url http://localhost:9000 --concurrency 1 5 10
```
This reuses the identical benchmark harness and evaluation set — the two tables are directly comparable and both belong in the final submission.

## 8. Bonus-category status

- **Open-source contribution**: see the PR/issue drafted in `docs/opea_contribution.md`, ready to file against `opea-project/GenAIComps`.
- **Knowledge sharing**: a technical write-up is drafted in `docs/blog_post.md`, ready to publish.
- **Hardware optimization**: not yet claimed. NetGenie's mock-mode path has no local model inference to optimize (BM25 is pure-Python, SQL runs on SQLite); the honest way to earn this category is running the real-LLM path in Section 7 through an AMX/AVX-512-aware quantized runtime (e.g. `llama.cpp` built with `-DGGML_AVX512=ON`, or OpenVINO INT8) and reporting the before/after delta. This requires hardware we don't have access to in this environment — see the guidance we provided outside this repo for exact commands.
