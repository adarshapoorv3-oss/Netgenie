# Copyright 2026 NetGenie Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Thin OpenAI-compatible chat client shared by every worker.

Real backends talk to ANY OpenAI-compatible /v1/chat/completions endpoint
(Ollama, Groq, vLLM, TGI's OpenAI shim, a hosted API...) so the same code
runs on a laptop or a Xeon/Gaudi cluster without changes -- this mirrors
the OpenAI-compatible endpoint pattern OPEA's own agent components use.

Mock mode returns deterministic, template-based text with no network
call at all, so the mega-service is fully runnable offline.

Unlike a single fixed instance-level backend, `chat()`/`chat_json()`
resolve their backend PER CALL via `settings.resolve_backend(backend_id)`
so a single running process can serve mock, local-Ollama, and Groq
requests side by side -- this is what lets the UI expose a live backend
picker instead of requiring a restart to switch backends.
"""
import json
import httpx

from services.common.config import settings


class LLMClient:
    def chat(self, messages, backend: str | None = None, temperature: float = 0.2, max_tokens: int = 512) -> str:
        cfg = settings.resolve_backend(backend)
        if cfg["mock"]:
            note = ""
            if cfg.get("requested_unavailable"):
                note = f"[requested backend '{cfg['requested_unavailable']}' unavailable, using mock] "
            return note + self._mock_reply(messages)

        try:
            resp = httpx.post(
                f"{cfg['base_url'].rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
                json={
                    "model": cfg["model"],
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=settings.LLM_TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # network down, bad model name, cold-load timeout, etc.
            return (
                "[llm-unavailable] Falling back to extractive answer. "
                f"(backend={cfg['id']}, {type(exc).__name__}: {exc})"
            )

    def chat_json(self, messages, backend: str | None = None, temperature: float = 0.0, max_tokens: int = 256) -> dict:
        """Ask the model for strict JSON and parse it, with a safe fallback."""
        raw = self.chat(messages, backend=backend, temperature=temperature, max_tokens=max_tokens)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except Exception:
            return {}

    @staticmethod
    def _mock_reply(messages) -> str:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        return (
            "[mock-llm] This is a deterministic offline reply used because "
            "the 'mock' backend is selected. It reasoned over: "
            f"\"{last_user[:160]}\""
        )


llm_client = LLMClient()
