# OPEA open-source contribution (drafted, not yet filed)

This is written to file as a GitHub issue (or a docs PR) against
`opea-project/GenAIComps`. It documents a real gap we hit integrating
NetGenie: nothing in the top-level README or PyPI page for `opea-comps`
explains how to register an **already-running, independently deployed**
microservice into a `ServiceOrchestrator` DAG purely for orchestration
(as opposed to `MicroService` also hosting a server itself).

We found the answer by reading `comps/cores/mega/micro_service.py` source
directly (`use_remote_service=True` skips the whole server-hosting block),
not from any doc page. That's a natural stumbling block for anyone
composing OPEA's orchestrator with services that already have their own
deployment lifecycle (their own Dockerfile, their own CI, their own
non-OPEA host) — which is a very common integration shape outside of
OPEA's own bundled examples.

---

## Draft issue text

**Title:** Document `MicroService(use_remote_service=True)` for
orchestrating already-deployed / externally-hosted services

**Body:**

When building a `ServiceOrchestrator` DAG for services that are already
running as independent processes (their own container, their own
deployment, possibly not even written against `comps.MicroService`'s
`@register_microservice` decorator), constructing a plain
`MicroService(name=..., host=..., port=...)` node attempts to bind and
host a server on that host:port — which collides with the real service
already listening there.

`use_remote_service=True` solves this cleanly (it skips the entire
server-hosting branch of `__init__`, leaving the object as a pure
registration/metadata handle for `ServiceOrchestrator.add()` /
`.flow_to()` / `.downstream()`), but this isn't mentioned in the README's
Megaservice/Gateway walkthrough, and none of the `GenAIExamples` we
looked at use it explicitly enough to be discoverable by example.

**Suggested fix:** a short "Registering an externally-hosted service"
subsection under the Megaservice docs, with a minimal example:

```python
from comps import MicroService, ServiceOrchestrator, ServiceRoleType, ServiceType

orchestrator = ServiceOrchestrator()
external_retriever = MicroService(
    name="my_retriever",
    host="retriever.internal",
    port=6002,
    endpoint="/v1/retrieve",
    service_role=ServiceRoleType.MICROSERVICE,
    service_type=ServiceType.RETRIEVER,
    use_remote_service=True,   # <-- this is the part that isn't documented
)
orchestrator.add(external_retriever)
```

We're happy to open this as a docs PR ourselves against the README (or
wherever maintainers prefer) rather than just filing the issue — flagging
both options here since the choice affects which we submit.

---

## Status

Not yet filed — filing requires a GitHub account with write access to
open issues/PRs on `opea-project/GenAIComps`, which has to happen from
your account, not from this environment. See the top-level guide for the
exact steps.
