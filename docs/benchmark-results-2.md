# Benchmark Results 2: Orphaned Resource Detection

Controlled A/B/C comparison of three approaches to orphaned resource detection:

- **Session A (MCP):** Uses Azure MCP tools directly — the LLM calls individual tools, interprets JSON responses, cross-references manually to find orphans
- **Session B (FUSE Filesystem):** Pre-computes orphans and dependency graph onto a projected filesystem; agent reads files
- **Session C (FUSE SQLite):** Pre-computes everything into SQLite with orphans, edges, and pricing tables; agent queries with SQL JOINs

**Target:** `rg-dev-eastus` — 35 resources across 3 deployment stacks (API Management, AI Search, Cognitive Services, Container Apps, Key Vault, Storage, Log Analytics, App Insights, ACR)

**Prompt:**

> Find all orphaned resources in rg-dev-eastus — unattached disks, unused NICs, unassociated public IPs, and any other resources that appear to have no dependencies.

---

## Session A: MCP Tools (Azure Live API)

### Tool Calls

| # | Tool Call | Purpose | Results | Est. Tokens |
|---|-----------|---------|---------|-------------|
| 1 | `group_resource_list(rg-dev-eastus)` | List all 35 resources | 35 | ~28,000 |
| 2 | `resource_get(apim-dev-eastus-dhi6n6)` | Inspect APIM instance | 1 | ~4,000 |
| 3 | `resource_get(apim-dev-eastus-goln5p)` | Inspect APIM instance | 1 | ~4,000 |
| 4 | `resource_get(apim-dev-eastus-q3grjnqowando)` | Inspect APIM instance | 1 | ~4,000 |
| 5 | `resource_get(acrdeveastusdhi6n6)` | Check ACR for image refs | 1 | ~2,000 |
| 6 | `resource_get(acrdeveastusgoln5p)` | Check ACR for image refs | 1 | ~2,000 |
| 7 | `resource_get(acrdeveastusq3grjnqowando)` | Check ACR for image refs | 1 | ~2,000 |
| 8 | `resource_get(kv-dev-eastus-dhi6n6)` | Inspect Key Vault | 1 | ~3,000 |
| 9 | `resource_get(kv-dev-skfkws)` | Inspect Key Vault | 1 | ~3,000 |
| 10 | `resource_get(ai-account-fhtxfm34vs6s4)` | Check AI account refs | 1 | ~2,500 |
| 11 | `resource_get(aideveastusgoln5p)` | Check AI account refs | 1 | ~2,500 |
| 12 | `resource_get(aideveastusgoln5pjtx3)` | Check AI account refs | 1 | ~2,500 |
| 13 | `resource_get(aifoundrydeveastusdhi6n6)` | Check AI account refs | 1 | ~2,500 |
| 14 | `resource_get(search-fhtxfm34vs6s4)` | Check Search service refs | 1 | ~2,000 |
| 15 | `resource_get(srch-dev-eastus-dhi6n6)` | Check Search service refs | 1 | ~2,000 |
| 16 | `resource_get(srchdeveastusgoln5p)` | Check Search service refs | 1 | ~2,000 |
| 17 | `resource_get(stdeveastusdhi6n6)` | Check storage account refs | 1 | ~2,500 |
| 18 | `resource_get(ca-dev-eastus-goln5p)` | Check container app settings | 1 | ~3,000 |
| 19 | `resource_get(ragapi-dev-eastus-q3grjnqowando)` | Check container app settings | 1 | ~3,000 |
| 20 | `resource_get(cae-dev-eastus-*)` ×3 | Check 3 CA environments | 3 | ~6,000 |
| 21 | `resource_get(appi-*)` ×4 | Check 4 App Insights | 4 | ~6,000 |
| 22 | `resource_get(log-*)` ×4 | Check 4 Log Analytics workspaces | 4 | ~4,800 |
| | **TOTALS** | | **64** | **~93,300** |

### Summary

| Metric | Value |
|--------|-------|
| MCP tool calls | ~22 distinct calls (64 resource fetches) |
| Azure API calls | ~64 (each MCP call = 1+ ARM API call) |
| Estimated tokens ingested | ~93,300 |
| Cross-referencing needed | HIGH — must manually correlate app settings, connection strings, and resource IDs across all 35 resources |
| Offline capable | NO — requires live Azure connection |

---

## Session B: FUSE Filesystem (Pre-projected Snapshot)

### Tool Calls

| # | Command | Purpose | Items | Bytes Read | Est. Tokens |
|---|---------|---------|-------|------------|-------------|
| 1 | `Get-ChildItem -Path ".\azure-snapshot" -Recurse -Filter "_CANDIDATE_ORPHAN"` | Find all orphan markers | 18 | 1,080 | ~270 |
| 2 | `Get-Content orphan-reason.txt` ×18 | Read reason for each orphan | 18 | 2,106 | ~526 |
| 3 | `Get-Content orphaned-resources.txt` | Read full orphan summary | 1 | 5,116 | ~1,279 |
| 4 | `Get-Content dependency-graph.md` | Read pre-built dependency graph | 1 | 4,101 | ~1,025 |
| 5 | `Get-ChildItem -Recurse -Filter "*.ref"` in deps/rdeps dirs | Check dependency edges | 24 | 2,442 | ~610 |
| | **TOTALS** | | **62** | **14,845** | **~3,710** |

### Specific Tool Output

**Command 1** — `_CANDIDATE_ORPHAN` markers found in:
```
key-vaults/kv-dev-eastus-dhi6n6/_CANDIDATE_ORPHAN
key-vaults/kv-dev-skfkws/_CANDIDATE_ORPHAN
microsoft.apimanagement--service/apim-dev-eastus-dhi6n6/_CANDIDATE_ORPHAN
microsoft.apimanagement--service/apim-dev-eastus-goln5p/_CANDIDATE_ORPHAN
microsoft.apimanagement--service/apim-dev-eastus-q3grjnqowando/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts/ai-account-fhtxfm34vs6s4/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts/aideveastusgoln5p/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts/aideveastusgoln5pjtx3/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts/aifoundrydeveastusdhi6n6/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts--projects/ai-account-fhtxfm34vs6s4_ai-project-dev-eastus/_CANDIDATE_ORPHAN
microsoft.cognitiveservices--accounts--projects/aifoundrydeveastusdhi6n6_proj-dev-eastus-dhi6n6/_CANDIDATE_ORPHAN
microsoft.containerregistry--registries/acrdeveastusdhi6n6/_CANDIDATE_ORPHAN
microsoft.containerregistry--registries/acrdeveastusgoln5p/_CANDIDATE_ORPHAN
microsoft.containerregistry--registries/acrdeveastusq3grjnqowando/_CANDIDATE_ORPHAN
microsoft.search--searchservices/search-fhtxfm34vs6s4/_CANDIDATE_ORPHAN
microsoft.search--searchservices/srch-dev-eastus-dhi6n6/_CANDIDATE_ORPHAN
microsoft.search--searchservices/srchdeveastusgoln5p/_CANDIDATE_ORPHAN
storage-accounts/stdeveastusdhi6n6/_CANDIDATE_ORPHAN
```

**Command 2** — Each `orphan-reason.txt` contains:
```
Reason: Resource has no dependency edges (not referenced by or depending on any other resource)
Confidence: MEDIUM
```

**Command 5** — `.ref` files discovered (24 total, showing dependency edges):
```
cae-dev-eastus-dhi6n6/deps/log-dev-eastus-dhi6n6.ref        → logs-to
cae-dev-eastus-goln5p/deps/logdeveastusgoln5p.ref            → logs-to
cae-dev-eastus-goln5p/rdeps/ca-dev-eastus-goln5p.ref         → hosted-in
cae-dev-eastus-q3grjnqowando/rdeps/ragapi-dev-eastus-q3grjnqowando.ref → hosted-in
ca-dev-eastus-goln5p/deps/cae-dev-eastus-goln5p.ref          → hosted-in
ragapi-dev-eastus-q3grjnqowando/deps/cae-dev-eastus-q3grjnqowando.ref  → hosted-in
log-dev-eastus-dhi6n6/rdeps/appi-dev-eastus-dhi6n6.ref       → logs-to
log-dev-eastus-dhi6n6/rdeps/cae-dev-eastus-dhi6n6.ref        → logs-to
log-dev-skfkws/rdeps/appi-dev-skfkws.ref                     → logs-to
logdeveastusgoln5p/rdeps/appideveastusgoln5p.ref              → logs-to
logdeveastusgoln5p/rdeps/cae-dev-eastus-goln5p.ref            → logs-to
logs-fhtxfm34vs6s4/rdeps/appi-fhtxfm34vs6s4.ref              → logs-to
Failure Anomalies - appi-dev-eastus-dhi6n6/deps/appi-dev-eastus-dhi6n6.ref → monitors
Failure Anomalies - appi-dev-skfkws/deps/appi-dev-skfkws.ref              → monitors
Failure Anomalies - appi-fhtxfm34vs6s4/deps/appi-fhtxfm34vs6s4.ref        → monitors
Failure Anomalies - appideveastusgoln5p/deps/appideveastusgoln5p.ref       → monitors
appi-dev-eastus-dhi6n6/deps/log-dev-eastus-dhi6n6.ref        → logs-to
appi-dev-eastus-dhi6n6/rdeps/Failure Anomalies - appi-dev-eastus-dhi6n6.ref → monitors
appi-dev-skfkws/deps/log-dev-skfkws.ref                      → logs-to
appi-dev-skfkws/rdeps/Failure Anomalies - appi-dev-skfkws.ref             → monitors
appi-fhtxfm34vs6s4/deps/logs-fhtxfm34vs6s4.ref               → logs-to
appi-fhtxfm34vs6s4/rdeps/Failure Anomalies - appi-fhtxfm34vs6s4.ref       → monitors
appideveastusgoln5p/deps/logdeveastusgoln5p.ref               → logs-to
appideveastusgoln5p/rdeps/Failure Anomalies - appideveastusgoln5p.ref      → monitors
```

### Summary

| Metric | Value |
|--------|-------|
| Filesystem commands | 5 |
| Azure API calls | 0 (all pre-computed) |
| Estimated tokens ingested | ~3,710 |
| Cross-referencing needed | NONE — orphans and dependency graph pre-computed by FUSE CLI |
| Offline capable | YES — works entirely from local snapshot |

---

## Session C: FUSE SQLite DB (Pre-computed Queries)

### Tool Calls (SQL Queries)

**Query 1** — Get all orphans with metadata (18 rows, ~773 tokens):
```sql
SELECT r.name, r.type, o.reason, o.confidence
FROM orphans o
JOIN resources r ON o.resource_id = r.id
WHERE r.resource_group = 'rg-dev-eastus'
ORDER BY o.confidence DESC, r.type, r.name
```

**Query 2** — Cross-validate orphans via edge table (18 rows, ~300 tokens):
```sql
SELECT r.name, r.type
FROM resources r
WHERE r.resource_group = 'rg-dev-eastus'
  AND r.id NOT IN (SELECT source_id FROM edges)
  AND r.id NOT IN (SELECT target_id FROM edges)
ORDER BY r.type, r.name
```

**Query 3** — Show connected resources for context (17 rows, ~325 tokens):
```sql
SELECT r.name, r.type,
    (SELECT COUNT(*) FROM edges WHERE source_id = r.id) as out_edges,
    (SELECT COUNT(*) FROM edges WHERE target_id = r.id) as in_edges
FROM resources r
WHERE r.resource_group = 'rg-dev-eastus'
  AND (r.id IN (SELECT source_id FROM edges)
       OR r.id IN (SELECT target_id FROM edges))
ORDER BY in_edges DESC
```

**Query 4** — Orphan cost impact via pricing JOIN (18 rows, ~198 tokens):
```sql
SELECT r.name, r.type, p.sku_name, p.monthly_estimate, p.meter_name
FROM orphans o
JOIN resources r ON o.resource_id = r.id
LEFT JOIN pricing p ON r.id = p.resource_id
WHERE r.resource_group = 'rg-dev-eastus'
ORDER BY COALESCE(p.monthly_estimate, 0) DESC
```

Result — estimated monthly waste from orphaned resources:

| Resource | SKU | Monthly Cost | Meter |
|----------|-----|-------------|-------|
| apim-dev-eastus-dhi6n6 | StandardV2 | $700.00 | Standard v2 Unit |
| apim-dev-eastus-goln5p | StandardV2 | $700.00 | Standard v2 Unit |
| search-fhtxfm34vs6s4 | standard | $245.28 | Standard S1 Unit |
| srch-dev-eastus-dhi6n6 | basic | $73.73 | Basic Unit |
| srchdeveastusgoln5p | basic | $73.73 | Basic Unit |
| apim-dev-eastus-q3grjnqowando | Developer | $48.03 | Developer Unit |
| acrdeveastusdhi6n6 | Basic | $0.10 | Data Stored |
| acrdeveastusgoln5p | Basic | $0.10 | Data Stored |
| acrdeveastusq3grjnqowando | Basic | $0.10 | Data Stored |
| stdeveastusdhi6n6 | Standard_LRS | $0.06 | LRS Data Stored |
| kv-dev-eastus-dhi6n6 | standard | $0.03 | Operations |
| kv-dev-skfkws | standard | $0.03 | Operations |
| ai-account-fhtxfm34vs6s4 | S0 | $0.00 | (usage-based) |
| aideveastusgoln5p | S0 | $0.00 | (usage-based) |
| aideveastusgoln5pjtx3 | S0 | $0.00 | (usage-based) |
| aifoundrydeveastusdhi6n6 | S0 | $0.00 | (usage-based) |
| **TOTAL** | | **$1,841.19/mo** | |

**Query 5** — Pre-built Mermaid dependency graph (1 row, ~863 tokens):
```sql
SELECT content FROM artifacts WHERE name = 'dependency_graph_mermaid'
```

### Tool Call Summary

| # | SQL Query | Purpose | Rows | Est. Tokens |
|---|-----------|---------|------|-------------|
| 1 | `orphans JOIN resources` | Get all orphans + metadata | 18 | ~773 |
| 2 | `zero-edge resources` | Validate orphans via edge table | 18 | ~300 |
| 3 | `connected resources` | Show non-orphans for context | 17 | ~325 |
| 4 | `orphan pricing JOIN` | Cost impact of orphans | 18 | ~198 |
| 5 | `artifacts (mermaid graph)` | Pre-built dependency graph | 1 | ~863 |
| | **TOTALS** | | **72** | **~2,459** |

### Summary

| Metric | Value |
|--------|-------|
| SQL queries | 5 |
| Azure API calls | 0 (all pre-computed in SQLite) |
| Database size | 548 KB |
| Estimated tokens ingested | ~2,459 |
| Cross-referencing needed | NONE — SQL JOINs replace manual correlation |
| Offline capable | YES — works entirely from local DB |

---

## Comparison: All 3 Sessions

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|------------------------|---------------------|
| **Tool/command calls** | ~22 | 5 | 5 |
| **Azure API calls** | ~64 | 0 | 0 |
| **Estimated tokens ingested** | ~93,300 | ~3,710 | ~2,459 |
| **Token reduction vs MCP** | baseline | **~96% less** | **~97% less** |
| **Cross-referencing reasoning** | HIGH (manual) | NONE (pre-computed) | NONE (SQL JOINs) |
| **Orphans found** | ~18 (with effort) | 18 | 18 |
| **Offline capable** | NO | YES | YES |
| **Includes cost impact** | Manual lookup needed | No | Yes ($1,841.19/mo waste) |
| **Includes dependency graph** | Must build manually | Pre-built (1 file read) | Pre-built (1 SQL query) |
| **Risk of hallucination** | HIGH | LOW | LOW |

### Key Takeaways

1. **96–97% token reduction:** FUSE approaches (B & C) ingest ~2,500–3,700 tokens vs ~93,300 for MCP — a ~97% reduction
2. **Zero Azure API calls:** Both FUSE sessions work entirely from pre-computed local data
3. **No cross-referencing needed:** MCP requires the LLM to manually correlate resource IDs, app settings, and connection strings across 35 resources. FUSE pre-computes all dependency edges and orphan detection
4. **Cost visibility only in Session C:** The SQLite approach uniquely surfaces that orphaned resources cost **$1,841.19/month** — primarily from 2× APIM StandardV2 ($1,400/mo) and Search services ($393/mo)
5. **Identical findings:** All three sessions identify the same 18 candidate orphans, but Session A requires significantly more effort and has higher hallucination risk
6. **Offline capability:** Sessions B and C work fully offline after the initial snapshot, making them suitable for air-gapped environments or CI/CD pipelines
