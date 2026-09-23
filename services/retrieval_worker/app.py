# Copyright 2026 NetGenie Contributors
# SPDX-License-Identifier: Apache-2.0
"""
NetGenie / OPEA Retrieval worker.

Owns the runbook knowledge base. Loads and indexes data/runbooks/*.md
at startup and answers top-k lexical retrieval requests for the
supervisor agent in the gateway.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from services.common.config import settings
from services.retrieval_worker.ingest import BM25Index

_index: BM25Index | None = None


def load_index():
    global _index
    _index = BM25Index(settings.RUNBOOKS_DIR)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_index()
    yield


app = FastAPI(title="netgenie-retrieval-worker", version="1.0.0", lifespan=lifespan)


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 3


class RetrieveResult(BaseModel):
    source: str
    heading: str
    text: str
    score: float


class RetrieveResponse(BaseModel):
    results: list[RetrieveResult]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "retrieval_worker",
        "chunks_indexed": len(_index.chunks) if _index else 0,
    }


@app.post("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest):
    if _index is None:
        return RetrieveResponse(results=[])
    hits = _index.search(req.query, top_k=req.top_k)
    return RetrieveResponse(results=[RetrieveResult(**h) for h in hits])


@app.post("/v1/reindex")
def reindex():
    load_index()
    return {"status": "reindexed", "chunks_indexed": len(_index.chunks) if _index else 0}
