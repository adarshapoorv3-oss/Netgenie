"""
NetGenie / OPEA Guardrails microservice.

A lightweight, dependency-free safety layer that every message passes
through twice: once as user input (block prompt-injection / abuse) and
once as tool/model output (redact PII before it reaches the operator).

This is a simplified stand-in for OPEA's guardrails component -- same
role in the pipeline, sized to run on a 4-core CPU with no model
download.
"""
import re
import time

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="netgenie-guardrails", version="1.0.0")

# --- detection patterns ---------------------------------------------------
PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "imsi": re.compile(r"\b\d{15}\b"),  # telecom subscriber identifiers
}

INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|the)?\s*(previous|above|prior) instructions", re.I),
    re.compile(r"you are now (in )?(developer|jailbreak|dan) mode", re.I),
    re.compile(r"disregard (your|the) (system|safety) prompt", re.I),
    re.compile(r"reveal (your|the) (system prompt|api key|credentials)", re.I),
]

BANNED_TOPICS = [
    re.compile(r"\bhow (do|can) i (bypass|disable) (the )?firewall\b", re.I),
    re.compile(r"\bexploit\b.*\bvulnerabilit", re.I),
]


class ScreenRequest(BaseModel):
    text: str
    direction: str = "input"  # "input" (user->system) or "output" (tool/model->user)


class ScreenResponse(BaseModel):
    allowed: bool
    reason: str | None = None
    redacted_text: str
    findings: list[str]
    latency_ms: float


def _redact(text: str) -> tuple[str, list[str]]:
    findings = []
    redacted = text
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(redacted):
            findings.append(f"pii:{label}")
            redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)
    return redacted, findings


@app.get("/health")
def health():
    return {"status": "ok", "service": "guardrails"}


@app.post("/v1/screen", response_model=ScreenResponse)
def screen(req: ScreenRequest):
    t0 = time.perf_counter()
    findings: list[str] = []
    allowed = True
    reason = None

    if req.direction == "input":
        for pat in INJECTION_PATTERNS:
            if pat.search(req.text):
                allowed = False
                reason = "prompt_injection_pattern_detected"
                findings.append("injection")
                break
        if allowed:
            for pat in BANNED_TOPICS:
                if pat.search(req.text):
                    allowed = False
                    reason = "policy_violation"
                    findings.append("banned_topic")
                    break

    redacted, pii_findings = _redact(req.text)
    findings.extend(pii_findings)

    return ScreenResponse(
        allowed=allowed,
        reason=reason,
        redacted_text=redacted,
        findings=findings,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
