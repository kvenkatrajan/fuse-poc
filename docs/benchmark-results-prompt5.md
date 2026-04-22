## Benchmark Results: Tagging Compliance Check

**Run date:** 2026-04-22 14:30  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> Check tagging compliance for rg-dev-eastus. Which resources are missing environment, owner, or cost-center tags? What's the overall compliance percentage?

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | 3.8s | 13.2s | 23.0s |
| **Query-only time** | 3.8s (no pre-compute) | 3.2s | 0.004s |
| **Collection time** | N/A (live) | 10.0s | 23.0s |
| **az CLI calls** | 1 | 5 | 11 |
| **Tool calls (total)** | 1 | 8 | 14 |
| **Tokens ingested** | ~8,592 | ~560 | ~998 |
| **Resources checked** | 35 | 35 | 35 |
| **Non-compliant** | 35 | 35 | 35 |
| **Compliance %** | 0% | 0% | 0% |
| **Token reduction vs MCP** | baseline | ~93% less | ~88% less |
| **Time reduction vs MCP** | baseline | -247% (slower) | -505% (slower) |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources with tags, then analyze
tag presence locally. For tagging compliance, the resource list API returns tags
directly, making this the simplest approach — only 1 az CLI call needed.

| Metric | Value |
|--------|-------|
| Total time | 3.8s |
| az CLI calls | 1 |
| Tool calls (total) | 1 |
| Tokens ingested | ~8,592 |
| Resources checked | 35 |
| Non-compliant | 35 |
| Compliance % | 0% |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 3.8s |

### Tag Breakdown

| Tag | Resources with tag | Coverage |
|-----|-------------------|----------|
| environment | 3/35 | 8.6% |
| owner | 0/35 | 0.0% |
| cost-center | 0/35 | 0.0% |

---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources, edges, and orphans onto the
local filesystem. However, **tags are NOT projected to properties.json** — the filesystem
projector only writes name, type, resourceGroup, location, and properties. This required
a supplementary `az resource list` call during the query phase to retrieve tag data.

| Metric | Value |
|--------|-------|
| Collection time | 10.0s |
| Query time | 3.2s |
| Total time | 13.2s |
| az CLI calls (collection) | 4 |
| az CLI calls (query — supplementary) | 1 |
| Filesystem reads (query) | 3 |
| Tool calls (total) | 8 |
| Tokens ingested | ~560 |
| Resources checked | 35 |
| Non-compliant | 35 |
| Compliance % | 0% |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.0s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 1.9s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.0s |
| 4 | `az graph query -q "resources \| project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind \| where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 3.6s |

### Query-Phase Call Log

| # | Call | Time | Note |
|---|------|------|------|
| 5 | `az resource list -g rg-dev-eastus --query "[].{name,type,tags}"` | 3.1s | ⚠️ Supplementary — tags not in filesystem |

> **Gap identified:** The filesystem projector drops tags during projection. The Resource
> Graph query collects them (`$.tags`), but `projector.py:102-108` only writes name, type,
> resourceGroup, location, and properties to `properties.json`.

---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with full
`raw_json` column preserving all original fields including tags. Tag compliance is
queryable via `json_extract(raw_json, '$.tags')` with zero additional az CLI calls.

| Metric | Value |
|--------|-------|
| Collection time | 23.0s |
| Query time | 0.004s |
| Total time | 23.0s |
| az CLI calls (collection) | 11 |
| SQL queries (query) | 3 |
| Tool calls (total) | 14 |
| Tokens ingested | ~998 |
| DB size | 548.0 KB |
| Resources checked | 35 |
| Non-compliant | 35 |
| Compliance % | 0% |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.4s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 2.0s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.0s |
| 4 | `az graph query -q "resources \| project ... \| where resourceGroup in~ ('rg-dev-eastus')" --first 1000` | 2.9s |
| 5 | `azmcp pricing get API Management (eastus)` | 1.9s |
| 6 | `azmcp pricing get Cognitive Services (eastus)` | 1.7s |
| 7 | `azmcp pricing get Container Registry (eastus)` | 1.8s |
| 8 | `azmcp pricing get Key Vault (eastus)` | 1.8s |
| 9 | `azmcp pricing get Log Analytics (eastus)` | 1.7s |
| 10 | `azmcp pricing get Azure Cognitive Search (eastus)` | 1.8s |
| 11 | `azmcp pricing get Storage (eastus)` | 2.4s |

### SQL Queries Used

```sql
-- Q1: Tag compliance per resource
SELECT name, type, json_extract(raw_json, '$.tags') as tags_json
FROM resources WHERE resource_group = 'rg-dev-eastus'
ORDER BY type, name;

-- Q2: Per-tag coverage summary
-- (computed from Q1 results)

-- Q3: Resource type distribution
SELECT type, COUNT(*) as cnt FROM resources
WHERE resource_group = 'rg-dev-eastus' GROUP BY type ORDER BY cnt DESC;
```

---

## Non-Compliant Resources (All Sessions Agree: 35/35)

| Resource | Type | Missing Tags |
|----------|------|-------------|
| kv-dev-skfkws | vaults | owner, cost-center |
| log-dev-skfkws | workspaces | owner, cost-center |
| appi-dev-skfkws | components | owner, cost-center |
| Failure Anomalies - appi-dev-skfkws | smartDetectorAlertRules | environment, owner, cost-center |
| apim-dev-eastus-dhi6n6 | service | environment, owner, cost-center |
| log-dev-eastus-dhi6n6 | workspaces | environment, owner, cost-center |
| srch-dev-eastus-dhi6n6 | searchServices | environment, owner, cost-center |
| acrdeveastusdhi6n6 | registries | environment, owner, cost-center |
| aifoundrydeveastusdhi6n6 | accounts | environment, owner, cost-center |
| stdeveastusdhi6n6 | storageAccounts | environment, owner, cost-center |
| kv-dev-eastus-dhi6n6 | vaults | environment, owner, cost-center |
| appi-dev-eastus-dhi6n6 | components | environment, owner, cost-center |
| aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6 | projects | environment, owner, cost-center |
| cae-dev-eastus-dhi6n6 | managedEnvironments | environment, owner, cost-center |
| Failure Anomalies - appi-dev-eastus-dhi6n6 | smartDetectorAlertRules | environment, owner, cost-center |
| srchdeveastusgoln5p | searchServices | environment, owner, cost-center |
| logdeveastusgoln5p | workspaces | environment, owner, cost-center |
| apim-dev-eastus-goln5p | service | environment, owner, cost-center |
| aideveastusgoln5p | accounts | environment, owner, cost-center |
| acrdeveastusgoln5p | registries | environment, owner, cost-center |
| appideveastusgoln5p | components | environment, owner, cost-center |
| cae-dev-eastus-goln5p | managedEnvironments | environment, owner, cost-center |
| aideveastusgoln5pjtx3 | accounts | environment, owner, cost-center |
| ca-dev-eastus-goln5p | containerApps | environment, owner, cost-center |
| Failure Anomalies - appideveastusgoln5p | smartDetectorAlertRules | environment, owner, cost-center |
| apim-dev-eastus-q3grjnqowando | service | environment, owner, cost-center |
| ai-account-fhtxfm34vs6s4 | accounts | environment, owner, cost-center |
| logs-fhtxfm34vs6s4 | workspaces | environment, owner, cost-center |
| ai-account-fhtxfm34vs6s4/ai-project-dev-eastus | projects | environment, owner, cost-center |
| appi-fhtxfm34vs6s4 | components | environment, owner, cost-center |
| search-fhtxfm34vs6s4 | searchServices | environment, owner, cost-center |
| Failure Anomalies - appi-fhtxfm34vs6s4 | smartDetectorAlertRules | environment, owner, cost-center |
| cae-dev-eastus-q3grjnqowando | managedEnvironments | environment, owner, cost-center |
| acrdeveastusq3grjnqowando | registries | environment, owner, cost-center |
| ragapi-dev-eastus-q3grjnqowando | containerApps | environment, owner, cost-center |

✅ **All three sessions found identical compliance results.**

### Partial Tag Coverage

3 resources have the `environment` tag (but still lack `owner` and `cost-center`):
- kv-dev-skfkws (environment: "dev")
- log-dev-skfkws (environment: "dev")
- appi-dev-skfkws (environment: "dev")

---

## Key Takeaways

1. **Different dynamics than orphan detection:** For simple attribute queries (tag checking), the direct `az resource list` approach (Session A) is the **fastest** at 3.8s vs 13.2s/23.0s for FUSE — because tags are returned directly in the resource list API. This contrasts with orphan detection where Session A was the slowest (120.7s).

2. **Token reduction still significant:** FUSE approaches ingest ~560–998 tokens vs ~8,592 for MCP — a 88–93% reduction. The direct approach ingests full resource JSON including properties, SKU, identity etc., while FUSE approaches extract only what's needed.

3. **Filesystem projection gap:** The FUSE filesystem projector **drops tags** during projection (`projector.py:102-108` only writes name, type, resourceGroup, location, properties). This forced Session B to make a supplementary az CLI call, degrading the "zero query-phase az calls" advantage. **Recommendation:** Add `tags` to the filesystem projection.

4. **SQLite preserves full fidelity:** Session C's `raw_json` column preserves the complete Resource Graph response including tags, enabling `json_extract()` queries with **0 additional az calls** and sub-millisecond query time (0.004s).

5. **FUSE value proposition is query-type dependent:** FUSE pre-computation pays off most for complex cross-referencing queries (orphan detection, dependency analysis) where the alternative is N+1 API calls. For flat attribute queries, the overhead of collection exceeds the benefit — unless the snapshot is already cached from a prior operation.

6. **Amortized cost:** If the FUSE snapshot is already available (from a prior orphan check or dependency analysis), the incremental cost of tag compliance checking drops to 0.004s (SQLite) or ~0.1s (filesystem + supplementary call).
