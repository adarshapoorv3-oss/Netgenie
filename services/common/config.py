"""
Shared configuration for all NetGenie OPEA microservices.
Every service reads the same environment variables so the whole
mega-service can be reconfigured from one .env file.
"""
import os


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- LLM backend -------------------------------------------------
    # MOCK_LLM=true lets the whole mega-service run with zero external
    # dependencies (no model download, no API key) so judges can get a
    # working demo in well under the 10-minute clean-install budget.
    # Kept for backward compatibility -- DEFAULT_BACKEND below is now the
    # authoritative default, and each /v1/chat request can override it.
    MOCK_LLM: bool = _bool("MOCK_LLM", True)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "not-needed")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.1:8b")
    LLM_TIMEOUT_S: float = float(os.getenv("LLM_TIMEOUT_S", "30"))

    # --- multi-backend selection ---------------------------------------
    # NetGenie can run three interchangeable LLM backends behind the same
    # OpenAI-compatible client, selectable PER REQUEST from the UI (see
    # /v1/backends and the "backend" field on /v1/chat):
    #   mock  -- deterministic offline template, zero dependencies
    #   local -- small model on your own Ollama container (default 3B --
    #            fast enough for CPU-only demos, still fully local/private)
    #   groq  -- Groq's hosted OpenAI-compatible API running a much larger
    #            model (default 70B) for noticeably higher answer quality,
    #            at the cost of needing an API key and network access
    DEFAULT_BACKEND: str = os.getenv("DEFAULT_BACKEND", "mock")

    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://ollama:11434/v1")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "llama3.2:3b")
    LOCAL_LLM_API_KEY: str = os.getenv("LOCAL_LLM_API_KEY", "not-needed")

    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    @property
    def BACKENDS(self) -> dict:
        """Registry of selectable LLM backends. `available` reflects
        whether this backend can actually be called right now (e.g. Groq
        needs an API key present) -- the UI uses this to grey out options
        rather than let the user pick something that will just fail."""
        return {
            "mock": {
                "label": "Mock (offline, deterministic)",
                "mock": True,
                "available": True,
            },
            "local": {
                "label": f"Local Ollama ({self.LOCAL_LLM_MODEL})",
                "mock": False,
                "base_url": self.LOCAL_LLM_BASE_URL,
                "model": self.LOCAL_LLM_MODEL,
                "api_key": self.LOCAL_LLM_API_KEY,
                "available": True,  # can't cheaply verify the model is pulled without a call; container reachability is checked at call time
            },
            "groq": {
                "label": f"Groq ({self.GROQ_MODEL})",
                "mock": False,
                "base_url": self.GROQ_BASE_URL,
                "model": self.GROQ_MODEL,
                "api_key": self.GROQ_API_KEY,
                "available": bool(self.GROQ_API_KEY),
            },
        }

    def resolve_backend(self, backend_id: str | None) -> dict:
        backends = self.BACKENDS
        chosen = backend_id if backend_id in backends else self.DEFAULT_BACKEND
        cfg = backends.get(chosen, backends["mock"])
        if not cfg.get("available", True):
            # e.g. groq requested but no API key configured -- degrade to
            # mock rather than fail the whole request over a missing key
            cfg = {**backends["mock"], "requested_unavailable": chosen}
        return {"id": chosen, **cfg}

    # --- gateway -> worker HTTP timeout --------------------------------
    # When a real backend is selected, the telemetry worker's own
    # /v1/query call makes an internal LLM call (NL->SQL). On a cold
    # Ollama start the model has to load into memory before it generates
    # anything, which can comfortably exceed 30s on CPU -- so the
    # gateway's timeout for calling *workers* needs its own, more
    # generous budget than a single LLM call, not the same 30s. Override
    # via WORKER_TIMEOUT_S if your hardware is slower still.
    WORKER_TIMEOUT_S: float = float(os.getenv("WORKER_TIMEOUT_S", "90"))

    # --- service discovery --------------------------------------------
    GUARDRAILS_URL: str = os.getenv("GUARDRAILS_URL", "http://localhost:6001")
    RETRIEVAL_URL: str = os.getenv("RETRIEVAL_URL", "http://localhost:6002")
    TELEMETRY_URL: str = os.getenv("TELEMETRY_URL", "http://localhost:6003")

    # --- data paths ------------------------------------------------------
    RUNBOOKS_DIR: str = os.getenv("RUNBOOKS_DIR", "data/runbooks")
    KPI_DB_PATH: str = os.getenv("KPI_DB_PATH", "data/telemetry.db")

    # --- ports -----------------------------------------------------------
    GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "9000"))
    GUARDRAILS_PORT: int = int(os.getenv("GUARDRAILS_PORT", "6001"))
    RETRIEVAL_PORT: int = int(os.getenv("RETRIEVAL_PORT", "6002"))
    TELEMETRY_PORT: int = int(os.getenv("TELEMETRY_PORT", "6003"))


settings = Settings()
