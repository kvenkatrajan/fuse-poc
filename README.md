# Azure FUSE — SQLite Projection for Azure Resource Analysis

A pre-computation layer that snapshots Azure resources into a **SQLite database** with dependency graphs, orphan detection, and retail pricing — enabling sub-second analysis queries instead of dozens of slow MCP/API calls.

## Why

Answering questions like *"what depends on this Key Vault?"* or *"which resources are expensive?"* currently requires 10–30+ individual MCP tool calls, each taking 3–10 seconds, with heavy LLM reasoning to cross-reference results.

FUSE collects everything once (~23 seconds), projects it into SQLite, and then any question is a SQL query that returns in milliseconds.

| Approach | Time | Tool calls | Pricing accuracy |
|----------|------|------------|-----------------|
| MCP tools (Session A) | 60–293s | 14–30+ | ✅ Exact |
| **FUSE + SQLite (Session B)** | **0.01s query** (23s collect) | **1 SQL** | **✅ Exact** |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Collect resources (requires az CLI login)
az login
python -m azure_fuse.cli --mcp \
  --subscription "My-Subscription" \
  --resource-groups rg-dev-eastus \
  --format sqlite \
  --output ./azure-fuse

# Query the database
sqlite3 ./azure-fuse/My-Subscription.db "SELECT name, type FROM resources"
```

## What Gets Collected

In a single ~23s collection run:

- **35 resources** with full ARM properties (JSON)
- **12 dependency edges** (Key Vault refs, subnet associations, etc.)
- **18 orphan candidates** with reasons and confidence scores
- **Mermaid dependency graph** (ready to render)
- **Retail pricing** for all SKU-bearing resources via `azmcp` CLI
- **Tags** for compliance auditing

## Architecture

```
az graph query ──→ Resources (JSON)
                      │
                      ├── relationships.py ──→ Edges + Orphans
                      │
                      ├── pricing.py ──→ azmcp pricing get ──→ Pricing table
                      │
                      └── sqlite_projector.py ──→ SQLite DB
                              │
                              ├── resources (35 rows, full JSON)
                              ├── edges (12 dependency relationships)
                              ├── orphans (18 candidates)
                              ├── pricing (20 retail price entries)
                              └── artifacts (Mermaid graph)
```

## Key SQL Queries

```sql
-- Resource inventory
SELECT name, type, location FROM resources;

-- Orphaned resources with cost impact
SELECT r.name, r.type, o.reason, p.monthly_estimate
FROM orphans o
JOIN resources r ON o.resource_id = r.id
LEFT JOIN pricing p ON r.id = p.resource_id
ORDER BY COALESCE(p.monthly_estimate, 0) DESC;

-- Dependency graph (what depends on what?)
SELECT source_key, relationship, target_key FROM edges;

-- Impact analysis (what breaks if I delete X?)
SELECT e.source_key, e.relationship
FROM edges e WHERE e.target_key LIKE '%my-keyvault%';

-- Most expensive resources
SELECT resource_name, sku_name, retail_price, unit, monthly_estimate
FROM pricing WHERE monthly_estimate > 0
ORDER BY monthly_estimate DESC;

-- Tag compliance
SELECT r.name, json_extract(r.raw_json, '$.tags') as tags
FROM resources r
WHERE json_extract(r.raw_json, '$.tags.environment') IS NULL;

-- Security: public network access
SELECT r.name, r.type,
  json_extract(r.properties_json, '$.publicNetworkAccess') as public_access
FROM resources r
WHERE json_extract(r.properties_json, '$.publicNetworkAccess') = 'Enabled';

-- Mermaid dependency diagram
SELECT content FROM artifacts WHERE name = 'dependency_graph_mermaid';
```

## Documentation

- [SQLite Schema Reference](docs/sqlite-schema.md) — All tables, columns, and relationships
- [Benchmark Results](docs/benchmark-results.md) — A/B comparison across 4 audit scenarios
- [Pricing Enrichment](docs/pricing.md) — How retail pricing is collected and matched

## Collection Modes

| Flag | Source | Azure Connection |
|------|--------|-----------------|
| `--mcp` | `az graph query` + `az resource` | Required |
| `--demo` | Built-in mock data (35 resources) | None |
| `--from-snapshot` | Previously saved JSON | None |

## Project Structure

```
azure_fuse/
  cli.py                 # Entry point — orchestrates collection + projection
  mcp_collector.py       # Collects resources via az CLI / Resource Graph
  relationships.py       # Analyzes dependencies + detects orphans
  sqlite_projector.py    # Projects to SQLite database
  pricing.py             # Enriches with retail pricing via azmcp CLI
  demo_data.py           # Mock data for demo mode
  projector.py           # (Legacy) Filesystem projector

docs/
  sqlite-schema.md       # SQLite schema reference
  benchmark-results.md   # A/B test results across 4 scenarios
  pricing.md             # Pricing enrichment details
```
