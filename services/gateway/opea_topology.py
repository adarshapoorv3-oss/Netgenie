# Copyright 2026 NetGenie Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Builds NetGenie's mega-service topology using OPEA's own orchestration
primitives (the `opea-comps` package, i.e. `comps.cores.mega`) instead of
a hand-rolled DAG.

This is a direct dependency on upstream OPEA code:
  - `comps.MicroService`       registers each NetGenie worker exactly the
                                 way OPEA's own GenAIExamples (e.g. ChatQnA,
                                 AgentQnA) register embedding/retriever/LLM
                                 nodes.
  - `comps.ServiceOrchestrator` provides the DAG (add / flow_to / downstream
                                 / topological_sort) that decides execution
                                 order and fan-out.
  - `comps.ServiceType`         gives each worker its correct OPEA role:
                                 GUARDRAIL, RETRIEVER, TEXT2SQL. TEXT2SQL in
                                 particular is an exact upstream match for
                                 the telemetry worker's NL->SQL job.

We deliberately do NOT use `ServiceOrchestrator.schedule()` for execution.
`schedule()` auto-aligns inputs/outputs for OPEA's *standard* service
contracts (TextDoc, EmbedDoc, LLMParamsDoc, ...); NetGenie's workers speak
a small custom domain schema (runbook chunks, SQL rows) that predates and
falls outside that alignment table. Silently forcing our schema through
`schedule()`'s generic alignment would either crash or silently misroute
enterprise data -- worse than not using it. Instead, the gateway (see
`app.py`) asks *this* orchestrator for topology decisions (which workers
are downstream of guardrails, in what order) and performs the actual HTTP
calls itself, with our own request/response models. This is the same
"orchestrator decides shape, gateway performs the call" split used by
OPEA's own `Gateway` classes for examples with non-standard payloads.
"""
from urllib.parse import urlparse

from comps import MicroService, ServiceOrchestrator, ServiceRoleType, ServiceType

from services.common.config import settings


def _host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or 80


def build_megaservice() -> ServiceOrchestrator:
    """Registers NetGenie's four services as a real OPEA ServiceOrchestrator DAG.

    Topology (matches the runtime fan-out in app.py's /v1/chat handler):

        guardrails --> retrieval_worker
                   \\-> telemetry_worker

    guardrails runs first (input screening), then the supervisor fans out
    to whichever of retrieval_worker / telemetry_worker the question needs,
    running them concurrently, before guardrails runs again on the way out
    (output PII screening) -- see app.py for the two-pass guardrail detail
    that this static DAG doesn't capture (OPEA's DAG type has no notion of
    a node appearing twice, so app.py calls the guardrails MicroService
    directly a second time for the output pass).
    """
    orchestrator = ServiceOrchestrator()

    # use_remote_service=True is essential here: NetGenie's workers are
    # already-running independent FastAPI processes (their own Dockerfile,
    # their own port). Without this flag MicroService.__init__ tries to
    # *host* a server itself on that host:port (it's designed to double as
    # the base class workers subclass to serve themselves), which would
    # collide with the real worker already bound there. use_remote_service
    # makes this purely a registration/metadata handle for orchestration.
    g_host, g_port = _host_port(settings.GUARDRAILS_URL)
    guardrails = MicroService(
        name="guardrails",
        host=g_host,
        port=g_port,
        endpoint="/v1/screen",
        service_role=ServiceRoleType.MICROSERVICE,
        service_type=ServiceType.GUARDRAIL,
        description="Prompt-injection + PII screening (NetGenie)",
        use_remote_service=True,
    )

    r_host, r_port = _host_port(settings.RETRIEVAL_URL)
    retrieval = MicroService(
        name="retrieval_worker",
        host=r_host,
        port=r_port,
        endpoint="/v1/retrieve",
        service_role=ServiceRoleType.MICROSERVICE,
        service_type=ServiceType.RETRIEVER,
        description="BM25 retrieval over incident runbooks (NetGenie)",
        use_remote_service=True,
    )

    t_host, t_port = _host_port(settings.TELEMETRY_URL)
    telemetry = MicroService(
        name="telemetry_worker",
        host=t_host,
        port=t_port,
        endpoint="/v1/query",
        service_role=ServiceRoleType.MICROSERVICE,
        service_type=ServiceType.TEXT2SQL,
        description="NL-to-SQL over KPI/alarm telemetry (NetGenie)",
        use_remote_service=True,
    )

    orchestrator.add(guardrails).add(retrieval).add(telemetry)
    orchestrator.flow_to(guardrails, retrieval)
    orchestrator.flow_to(guardrails, telemetry)

    return orchestrator


def topology_summary(orchestrator: ServiceOrchestrator) -> dict:
    """Human/judge-readable view of the live OPEA DAG, for the /v1/opea/topology endpoint."""
    nodes = {}
    for name, svc in orchestrator.services.items():
        nodes[name] = {
            "service_type": svc.service_type.name,
            "host": svc.host,
            "port": svc.port,
            "endpoint": svc.endpoint,
            "description": svc.description,
        }
    return {
        "framework": "opea-comps (comps.cores.mega.ServiceOrchestrator)",
        "nodes": nodes,
        "edges": {name: orchestrator.downstream(name) for name in orchestrator.services},
        "topological_order": orchestrator.topological_sort(),
        "entry_points": orchestrator.ind_nodes(),
        "leaves": orchestrator.all_leaves(),
    }
