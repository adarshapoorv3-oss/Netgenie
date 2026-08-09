"""
NetGenie / OPEA Telemetry worker.

Answers natural-language questions about network KPIs and alarms by
translating them into SQL against a small SQLite warehouse -- the same
role as OPEA's DBQnA / Text2SQL examples, sized down for a single-node
CPU deployment.

Two translation modes:
  * MOCK_LLM=true  -> a small library of parameterized query templates
                       matched by keyword. Zero-dependency, deterministic,
                       good enough for the common NOC questions.
  * MOCK_LLM=false -> the LLM is given the schema and asked to produce a
                       single SELECT statement, which is then validated
                       (SELECT-only, whitelisted tables, no statement
                       chaining) before it ever touches the database.
"""
import os
import re
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from services.common.config import settings
from services.common.llm_client import llm_client
from services.telemetry_worker.seed_kpi import build as seed_build

ALLOWED_TABLES = {"regions", "cells", "kpi_daily", "alarms"}

SCHEMA_DESCRIPTION = """
regions(region_id INTEGER, region_name TEXT)
cells(cell_id INTEGER, cell_name TEXT, region_id INTEGER, tech TEXT)
kpi_daily(cell_id INTEGER, date TEXT, dropped_call_rate REAL, avg_latency_ms REAL,
          throughput_mbps REAL, congestion_pct REAL)
alarms(alarm_id INTEGER, cell_id INTEGER, ts TEXT, severity TEXT, alarm_type TEXT, status TEXT)
"""


def ensure_db():
    if not os.path.exists(settings.KPI_DB_PATH):
        seed_build(settings.KPI_DB_PATH)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_db()
    yield


app = FastAPI(title="netgenie-telemetry-worker", version="1.0.0", lifespan=lifespan)


def _connect():
    conn = sqlite3.connect(settings.KPI_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_sql(sql: str) -> bool:
    s = sql.strip().rstrip(";")
    if ";" in s:
        return False
    if not re.match(r"^\s*SELECT\b", s, re.I):
        return False
    banned = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA)\b", re.I)
    if banned.search(s):
        return False
    tables_used = set(re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", s, re.I))
    flat = {t for pair in tables_used for t in pair if t}
    return flat.issubset(ALLOWED_TABLES) if flat else True


# --- mock template router --------------------------------------------------
def _mock_to_sql(question: str) -> tuple[str, str]:
    q = question.lower()
    region_match = None
    for name in ["north", "south", "east", "west", "central"]:
        if name in q:
            region_match = name.capitalize()
            break

    if "alarm" in q:
        if "critical" in q:
            sql = (
                "SELECT a.severity, a.alarm_type, a.status, c.cell_name, r.region_name, a.ts "
                "FROM alarms a JOIN cells c ON a.cell_id=c.cell_id "
                "JOIN regions r ON c.region_id=r.region_id "
                "WHERE a.severity='critical' ORDER BY a.ts DESC LIMIT 20"
            )
            label = "Critical alarms (most recent first)"
        elif region_match:
            sql = (
                "SELECT a.severity, a.alarm_type, a.status, c.cell_name, a.ts "
                "FROM alarms a JOIN cells c ON a.cell_id=c.cell_id "
                "JOIN regions r ON c.region_id=r.region_id "
                f"WHERE r.region_name='{region_match}' ORDER BY a.ts DESC LIMIT 20"
            )
            label = f"Alarms in {region_match} region"
        else:
            sql = (
                "SELECT severity, COUNT(*) as count FROM alarms "
                "WHERE status='open' GROUP BY severity ORDER BY count DESC"
            )
            label = "Open alarm counts by severity"
        return sql, label

    if "congest" in q:
        sql = (
            "SELECT c.cell_name, r.region_name, ROUND(AVG(k.congestion_pct),1) as avg_congestion_pct "
            "FROM kpi_daily k JOIN cells c ON k.cell_id=c.cell_id "
            "JOIN regions r ON c.region_id=r.region_id "
            "GROUP BY c.cell_id ORDER BY avg_congestion_pct DESC LIMIT 10"
        )
        return sql, "Top 10 cells by average congestion"

    if "dropped call" in q or "drop rate" in q or "dropped_call" in q:
        where = f"WHERE r.region_name='{region_match}'" if region_match else ""
        sql = (
            "SELECT r.region_name, ROUND(AVG(k.dropped_call_rate),2) as avg_dropped_call_rate "
            "FROM kpi_daily k JOIN cells c ON k.cell_id=c.cell_id "
            f"JOIN regions r ON c.region_id=r.region_id {where} "
            "GROUP BY r.region_name ORDER BY avg_dropped_call_rate DESC"
        )
        label = f"Average dropped-call rate{' in ' + region_match if region_match else ' by region'}"
        return sql, label

    if "latency" in q:
        where = f"WHERE r.region_name='{region_match}'" if region_match else ""
        sql = (
            "SELECT r.region_name, ROUND(AVG(k.avg_latency_ms),1) as avg_latency_ms "
            "FROM kpi_daily k JOIN cells c ON k.cell_id=c.cell_id "
            f"JOIN regions r ON c.region_id=r.region_id {where} "
            "GROUP BY r.region_name ORDER BY avg_latency_ms DESC"
        )
        return sql, "Average latency by region"

    # generic fallback: a network health snapshot
    sql = (
        "SELECT r.region_name, ROUND(AVG(k.dropped_call_rate),2) as avg_dropped_call_rate, "
        "ROUND(AVG(k.congestion_pct),1) as avg_congestion_pct "
        "FROM kpi_daily k JOIN cells c ON k.cell_id=c.cell_id "
        "JOIN regions r ON c.region_id=r.region_id "
        "GROUP BY r.region_name ORDER BY avg_dropped_call_rate DESC"
    )
    return sql, "Network health snapshot by region"


def _llm_to_sql(question: str, backend: str | None) -> tuple[str, str]:
    prompt = [
        {
            "role": "system",
            "content": (
                "You translate telecom NOC questions into a single SQLite SELECT "
                "statement. Only use these tables:\n" + SCHEMA_DESCRIPTION +
                "\nRespond with JSON: {\"sql\": \"...\", \"label\": \"...\"}. "
                "SQL must be a single SELECT statement, no semicolons, no DML/DDL."
            ),
        },
        {"role": "user", "content": question},
    ]
    result = llm_client.chat_json(prompt, backend=backend)
    sql = result.get("sql", "")
    label = result.get("label", "Query result")
    if not sql or not _validate_sql(sql):
        return _mock_to_sql(question)
    return sql, label


class QueryRequest(BaseModel):
    question: str
    backend: str | None = None  # "mock" | "local" | "groq"; falls back to settings.DEFAULT_BACKEND


class QueryResponse(BaseModel):
    label: str
    sql: str
    columns: list[str]
    rows: list[dict]


@app.get("/health")
def health():
    exists = os.path.exists(settings.KPI_DB_PATH)
    return {"status": "ok", "service": "telemetry_worker", "db_ready": exists}


@app.post("/v1/query", response_model=QueryResponse)
def query(req: QueryRequest):
    use_mock = settings.resolve_backend(req.backend)["mock"]
    sql, label = _mock_to_sql(req.question) if use_mock else _llm_to_sql(req.question, req.backend)
    if not _validate_sql(sql):
        return QueryResponse(label="rejected_unsafe_query", sql=sql, columns=[], rows=[])

    conn = _connect()
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    return QueryResponse(label=label, sql=sql, columns=cols, rows=rows)


@app.post("/v1/reseed")
def reseed():
    seed_build(settings.KPI_DB_PATH)
    return {"status": "reseeded"}
