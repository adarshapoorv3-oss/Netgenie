"""
Generates a small, deterministic synthetic telecom KPI + alarms dataset
so the telemetry worker has something realistic to query out of the box.
No real subscriber or network data is used anywhere in this project.

Schema:
  regions(region_id, region_name)
  cells(cell_id, cell_name, region_id, tech)
  kpi_daily(cell_id, date, dropped_call_rate, avg_latency_ms,
            throughput_mbps, congestion_pct)
  alarms(alarm_id, cell_id, ts, severity, alarm_type, status)
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cells (
    cell_id INTEGER PRIMARY KEY,
    cell_name TEXT NOT NULL,
    region_id INTEGER NOT NULL,
    tech TEXT NOT NULL,
    FOREIGN KEY(region_id) REFERENCES regions(region_id)
);
CREATE TABLE IF NOT EXISTS kpi_daily (
    cell_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    dropped_call_rate REAL NOT NULL,
    avg_latency_ms REAL NOT NULL,
    throughput_mbps REAL NOT NULL,
    congestion_pct REAL NOT NULL,
    FOREIGN KEY(cell_id) REFERENCES cells(cell_id)
);
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id INTEGER PRIMARY KEY,
    cell_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    severity TEXT NOT NULL,
    alarm_type TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(cell_id) REFERENCES cells(cell_id)
);
"""

REGIONS = ["North", "South", "East", "West", "Central"]
TECHS = ["4G", "5G"]
ALARM_TYPES = [
    ("fiber_cut", "critical"),
    ("congestion", "major"),
    ("cell_outage", "critical"),
    ("hardware_fault", "major"),
    ("power_fluctuation", "minor"),
]


def build(db_path: str, seed: int = 42, days: int = 14, cells_per_region: int = 4):
    rng = random.Random(seed)
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    cur = conn.cursor()
    cell_id = 1
    cell_ids_by_region = {}
    for region_id, region in enumerate(REGIONS, start=1):
        cur.execute("INSERT INTO regions (region_id, region_name) VALUES (?, ?)", (region_id, region))
        cell_ids_by_region[region] = []
        for n in range(cells_per_region):
            tech = TECHS[n % len(TECHS)]
            cell_name = f"{region[:2].upper()}-{tech}-{n+1:02d}"
            cur.execute(
                "INSERT INTO cells (cell_id, cell_name, region_id, tech) VALUES (?, ?, ?, ?)",
                (cell_id, cell_name, region_id, tech),
            )
            cell_ids_by_region[region].append(cell_id)
            cell_id += 1

    # South region is deliberately degraded so demo queries have a story to tell.
    degraded_regions = {"South"}

    today = datetime.now(timezone.utc).date()
    all_cells = cur.execute("SELECT cell_id, region_id FROM cells").fetchall()
    region_name_by_id = {i + 1: r for i, r in enumerate(REGIONS)}

    for cid, region_id in all_cells:
        region = region_name_by_id[region_id]
        degraded = region in degraded_regions
        for d in range(days):
            date = (today - timedelta(days=days - d - 1)).isoformat()
            base_drop = rng.uniform(0.3, 1.2)
            base_lat = rng.uniform(18, 35)
            base_thr = rng.uniform(80, 220)
            base_cong = rng.uniform(10, 35)
            if degraded:
                # rising trend over the window to simulate an ongoing incident
                trend = d / max(days - 1, 1)
                base_drop += 2.5 * trend + rng.uniform(0, 0.5)
                base_lat += 25 * trend
                base_thr -= 40 * trend
                base_cong += 35 * trend
            cur.execute(
                """INSERT INTO kpi_daily
                   (cell_id, date, dropped_call_rate, avg_latency_ms, throughput_mbps, congestion_pct)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cid, date, round(base_drop, 2), round(base_lat, 1), round(base_thr, 1), round(base_cong, 1)),
            )

    # alarms: more/critical alarms concentrated in the degraded region
    alarm_id = 1
    now = datetime.now(timezone.utc)
    for cid, region_id in all_cells:
        region = region_name_by_id[region_id]
        n_alarms = rng.randint(3, 6) if region in degraded_regions else rng.randint(0, 2)
        for _ in range(n_alarms):
            atype, sev = rng.choice(ALARM_TYPES)
            ts = (now - timedelta(hours=rng.randint(0, 72))).isoformat(timespec="seconds")
            status = rng.choice(["open", "open", "acknowledged", "resolved"])
            cur.execute(
                """INSERT INTO alarms (alarm_id, cell_id, ts, severity, alarm_type, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (alarm_id, cid, ts, sev, atype, status),
            )
            alarm_id += 1

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/telemetry.db"
    build(path)
    print(f"Seeded synthetic telemetry DB at {path}")
