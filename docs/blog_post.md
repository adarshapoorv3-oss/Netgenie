# Building a Telecom NOC Copilot on OPEA: What Actually Wiring `ServiceOrchestrator` Taught Us

*Draft for dev.to / Medium / GitHub Discussions — edit the intro paragraph with your name/team before publishing.*

## The problem

A network operations engineer investigating rising congestion in a region
needs two things at once: the current numbers (which cells, how bad, what
trend) and the documented procedure for what to do about it. In most
telecom NOCs those live in two disconnected systems — a telemetry
dashboard and a runbook wiki — so engineers manually correlate them under
time pressure. We built **NetGenie**, a small OPEA-style application that
fuses both behind one conversational interface, with every step of its
reasoning shown, not hidden.

## Why "OPEA-style" and not "the exact OPEA examples"

Most public OPEA walkthroughs — ChatQnA, DocSum, AgentQnA — are
excellent generic templates, but none of them map cleanly onto "combine a
BM25 runbook search with a NL-to-SQL telemetry query, screen both ends for
safety, and return a numbered trace an operator can audit in ten
seconds." So we built four small FastAPI services (guardrails, a BM25
retriever, a text-to-SQL telemetry worker, and a supervisor gateway) that
mirror OPEA's microservice/mega-service split, and then made a deliberate
choice about how deep to go on actually depending on OPEA's own code.

## What we actually integrated, and why we stopped there

`opea-comps` (the PyPI package for `comps.cores.mega`, OPEA's
orchestration core) turned out to be genuinely lightweight — no `torch`,
no model weights, just FastAPI/orchestration-level dependencies. That
made it a safe, real dependency rather than a demo-only import: our
gateway now builds its worker fan-out DAG with an actual
`comps.ServiceOrchestrator`, registers each worker as a `comps.MicroService`
with the correct OPEA `ServiceType` (`GUARDRAIL`, `RETRIEVER`, and — a
nice exact match — `TEXT2SQL` for the telemetry worker), and asks that
orchestrator which workers are downstream of guardrails before deciding,
per question, which ones to actually call.

We deliberately *didn't* reach for `ServiceOrchestrator.schedule()` to
execute the calls. `schedule()` auto-aligns payloads for OPEA's standard
contracts (`TextDoc`, `EmbedDoc`, `LLMParamsDoc`...); our workers speak a
small custom domain schema — runbook chunks, SQL result rows — that
predates and falls outside that alignment table. Forcing it through would
have either crashed or silently misrouted data, which is worse than not
using it. So the orchestrator decides *topology*, and the gateway performs
the actual typed HTTP calls — the same split OPEA's own example
`Gateway` subclasses use whenever a payload shape doesn't fit the generic
path.

## The one non-obvious gotcha

`MicroService`'s constructor doubles as the base class OPEA workers
subclass to host themselves — so naively constructing one to *represent*
an already-running remote service tries to bind a second server on that
same host:port. The fix is `use_remote_service=True`, which skips the
whole server-hosting branch. We didn't find this documented anywhere; we
found it by reading `comps/cores/mega/micro_service.py` directly. We've
drafted a small docs contribution back to `GenAIComps` about this (see
`docs/opea_contribution.md` in the repo) — the fix is a one-line kwarg,
but it costs real time to discover blind.

## What we measured

Running the four services together end-to-end (not simulated) with the
built-in `eval/benchmark.py` harness, at concurrency 1/5/10:

| Concurrency | Success | Keyword-hit accuracy | Throughput | p50 | p95 |
|---|---|---|---|---|---|
| 1  | 100% | 100% | 21.9 req/s | 42 ms  | 77 ms  |
| 5  | 100% | 100% | 24.8 req/s | 209 ms | 329 ms |
| 10 | 100% | 100% | 24.5 req/s | 393 ms | 407 ms |

That's mock-LLM mode — no model inference, so it's measuring the
scaffolding (guardrails, BM25, SQL validation, orchestration) rather than
generation. We're publishing a second table against a real local model
once we've run it on real hardware; we'd rather show one honest number
than a fabricated one.

## What we'd do differently with more time

Dense-embedding retrieval as a fallback once the runbook library grows
past a few hundred documents; an actual anomaly-triggered mode where the
telemetry worker proactively flags KPI breaches instead of only answering
on request; and closing the loop by logging which suggested remediations
operators actually accepted, so the system's suggestions can be evaluated
against real outcomes over time.

Code: *[link to your GitHub repo once published]*
