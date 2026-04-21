"""
SQLite projector — writes Azure resource data to a single .db file.

Alternative to the filesystem projector that avoids Windows path length
limits and enables SQL-based querying by LLM skills.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from .relationships import resource_key


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resources (
    id              TEXT PRIMARY KEY,
    resource_key    TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    resource_group  TEXT,
    location        TEXT,
    raw_json        TEXT NOT NULL CHECK(json_valid(raw_json)),
    properties_json TEXT CHECK(properties_json IS NULL OR json_valid(properties_json))
);

CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(type);
CREATE INDEX IF NOT EXISTS idx_resources_rg   ON resources(resource_group);

CREATE TABLE IF NOT EXISTS edges (
    source_id    TEXT NOT NULL,
    target_id    TEXT NOT NULL,
    source_key   TEXT NOT NULL,
    target_key   TEXT NOT NULL,
    relationship TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, relationship),
    FOREIGN KEY (source_id) REFERENCES resources(id),
    FOREIGN KEY (target_id) REFERENCES resources(id)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

CREATE TABLE IF NOT EXISTS orphans (
    resource_id    TEXT PRIMARY KEY,
    reason         TEXT NOT NULL,
    confidence     TEXT NOT NULL,
    estimated_waste TEXT,
    FOREIGN KEY (resource_id) REFERENCES resources(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    name    TEXT PRIMARY KEY,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pricing (
    resource_id      TEXT PRIMARY KEY,
    resource_name    TEXT NOT NULL,
    resource_type    TEXT NOT NULL,
    sku_name         TEXT NOT NULL,
    service_name     TEXT NOT NULL,
    region           TEXT,
    retail_price     REAL NOT NULL DEFAULT 0,
    unit             TEXT,
    meter_name       TEXT,
    product_name     TEXT,
    monthly_estimate REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (resource_id) REFERENCES resources(id)
);
"""


def project_to_sqlite(
    db_path: Path,
    subscription: str,
    resources: List[dict],
    edges: List[Tuple[str, str, str]],
    orphans: List[dict],
    mermaid_graph: str,
    pricing: List[dict] = None,
) -> Path:
    """
    Write the full projection to a SQLite database.

    Returns the path to the created .db file.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file, then atomically replace — so concurrent readers
    # never see a partial/empty database.
    tmp_path = db_path.with_suffix(".db.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.executescript(SCHEMA)

        # --- Metadata ---
        meta = [
            ("subscription", subscription),
            ("projected_at", datetime.now(timezone.utc).isoformat()),
            ("resource_count", str(len(resources))),
            ("edge_count", str(len(edges))),
            ("orphan_count", str(len(orphans))),
        ]
        conn.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)", meta)

        # --- Resources ---
        # Build key→id lookup for edge insertion
        key_to_id = {}
        resource_rows = []
        for r in resources:
            rid = r.get("id", "")
            rkey = resource_key(r)
            key_to_id[rkey] = rid
            resource_rows.append((
                rid,
                rkey,
                r.get("name", ""),
                r.get("type", ""),
                r.get("resourceGroup", ""),
                r.get("location", ""),
                json.dumps(r, default=str),
                json.dumps(r.get("properties"), default=str) if r.get("properties") else None,
            ))

        conn.executemany(
            "INSERT OR IGNORE INTO resources (id, resource_key, name, type, resource_group, location, raw_json, properties_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            resource_rows,
        )

        # --- Edges ---
        edge_rows = []
        for src_key, tgt_key, rel in edges:
            src_id = key_to_id.get(src_key, src_key)
            tgt_id = key_to_id.get(tgt_key, tgt_key)
            edge_rows.append((src_id, tgt_id, src_key, tgt_key, rel))

        conn.executemany(
            "INSERT OR IGNORE INTO edges (source_id, target_id, source_key, target_key, relationship) "
            "VALUES (?, ?, ?, ?, ?)",
            edge_rows,
        )

        # --- Orphans ---
        orphan_rows = []
        for o in orphans:
            r = o["resource"]
            rid = r.get("id", "")
            orphan_rows.append((
                rid,
                o.get("reason", ""),
                o.get("confidence", "MEDIUM"),
                o.get("estimated_waste", ""),
            ))

        conn.executemany(
            "INSERT OR IGNORE INTO orphans (resource_id, reason, confidence, estimated_waste) "
            "VALUES (?, ?, ?, ?)",
            orphan_rows,
        )

        # --- Artifacts ---
        conn.execute(
            "INSERT INTO artifacts (name, content) VALUES (?, ?)",
            ("dependency_graph_mermaid", mermaid_graph),
        )

        # --- Pricing ---
        if pricing:
            pricing_rows = []
            for p in pricing:
                pricing_rows.append((
                    p.get("resource_id", ""),
                    p.get("resource_name", ""),
                    p.get("resource_type", ""),
                    p.get("sku_name", ""),
                    p.get("service_name", ""),
                    p.get("region", ""),
                    p.get("retail_price", 0),
                    p.get("unit", ""),
                    p.get("meter_name", ""),
                    p.get("product_name", ""),
                    p.get("monthly_estimate", 0),
                ))
            conn.executemany(
                "INSERT OR IGNORE INTO pricing "
                "(resource_id, resource_name, resource_type, sku_name, service_name, "
                "region, retail_price, unit, meter_name, product_name, monthly_estimate) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                pricing_rows,
            )

        conn.commit()
    finally:
        conn.close()

    # Atomic replace: readers never see a half-written DB
    import os
    os.replace(str(tmp_path), str(db_path))

    return db_path
