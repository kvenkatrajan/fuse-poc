## Benchmark Results 2 (v2): Orphaned Resource Detection

**Run date:** 2026-04-21 15:29  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> Find all orphaned resources in rg-dev-eastus — unattached disks, unused NICs, unassociated public IPs, and any other resources that appear to have no dependencies.

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | 120.7s | 9.4s | 21.8s |
| **Query-only time** | 120.7s (no pre-compute) | 0.13s | 0.008s |
| **Collection time** | N/A (live) | 9.3s | 21.8s |
| **az CLI calls** | 45 | 4 | 11 |
| **Tool calls (total)** | 45 | 26 | 16 |
| **Tokens ingested** | ~286,898 | ~3,474 | ~2,689 |
| **Orphans found** | 18 | 18 | 18 |
| **Token reduction vs MCP** | baseline | ~99% less | ~99% less |
| **Time reduction vs MCP** | baseline | ~92% less | ~82% less |
| **Monthly waste estimate** | N/A | N/A | $1841.19 |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources, then `az resource show` for each 
resource to get full properties, then manually cross-reference to find orphans.

| Metric | Value |
|--------|-------|
| Total time | 120.7s |
| az CLI calls | 45 |
| Tool calls (total) | 45 |
| Tokens ingested | ~286,898 |
| Orphans found | 18 |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 3.0s |
| 2 | `az resource show: kv-dev-skfkws` | 2.9s |
| 3 | `az resource show: log-dev-skfkws` | 3.1s |
| 4 | `az resource show: appi-dev-skfkws` | 2.8s |
| 5 | `az resource show: Failure Anomalies - appi-dev-skfkws` | 2.7s |
| 6 | `az resource show: apim-dev-eastus-dhi6n6` | 2.6s |
| 7 | `az resource show: log-dev-eastus-dhi6n6` | 2.7s |
| 8 | `az resource show: srch-dev-eastus-dhi6n6` | 2.8s |
| 9 | `az resource show: acrdeveastusdhi6n6` | 2.7s |
| 10 | `az resource show: aifoundrydeveastusdhi6n6` | 2.8s |
| 11 | `az resource show: stdeveastusdhi6n6` | 2.9s |
| 12 | `az resource show: kv-dev-eastus-dhi6n6` | 3.4s |
| 13 | `az resource show: appi-dev-eastus-dhi6n6` | 2.8s |
| 14 | `az resource show: aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6` | 2.7s |
| 15 | `az resource show: cae-dev-eastus-dhi6n6` | 2.9s |
| 16 | `az resource show: Failure Anomalies - appi-dev-eastus-dhi6n6` | 2.8s |
| 17 | `az resource show: srchdeveastusgoln5p` | 2.7s |
| 18 | `az resource show: apim-dev-eastus-goln5p` | 2.9s |
| 19 | `az resource show: logdeveastusgoln5p` | 2.7s |
| 20 | `az resource show: aideveastusgoln5p` | 2.7s |
| 21 | `az resource show: acrdeveastusgoln5p` | 2.8s |
| 22 | `az resource show: appideveastusgoln5p` | 2.8s |
| 23 | `az resource show: cae-dev-eastus-goln5p` | 2.9s |
| 24 | `az resource show: aideveastusgoln5pjtx3` | 2.6s |
| 25 | `az resource show: ca-dev-eastus-goln5p` | 3.4s |
| 26 | `az resource show: Failure Anomalies - appideveastusgoln5p` | 3.3s |
| 27 | `az resource show: apim-dev-eastus-q3grjnqowando` | 3.3s |
| 28 | `az resource show: ai-account-fhtxfm34vs6s4` | 2.8s |
| 29 | `az resource show: logs-fhtxfm34vs6s4` | 2.7s |
| 30 | `az resource show: ai-account-fhtxfm34vs6s4/ai-project-dev-eastus` | 3.1s |
| 31 | `az resource show: appi-fhtxfm34vs6s4` | 2.7s |
| 32 | `az resource show: search-fhtxfm34vs6s4` | 2.8s |
| 33 | `az resource show: Failure Anomalies - appi-fhtxfm34vs6s4` | 2.6s |
| 34 | `az resource show: cae-dev-eastus-q3grjnqowando` | 2.7s |
| 35 | `az resource show: acrdeveastusq3grjnqowando` | 2.8s |
| 36 | `az resource show: ragapi-dev-eastus-q3grjnqowando` | 3.3s |
| 37 | `azmcp pricing get Key Vault (eastus)` | 1.8s |
| 38 | `azmcp pricing get Log Analytics (eastus)` | 1.8s |
| 39 | `azmcp pricing get Application Insights (eastus)` | 1.8s |
| 40 | `azmcp pricing get API Management (eastus)` | 1.8s |
| 41 | `azmcp pricing get Azure Cognitive Search (eastus)` | 1.9s |
| 42 | `azmcp pricing get Container Registry (eastus)` | 1.8s |
| 43 | `azmcp pricing get Cognitive Services (eastus)` | 1.8s |
| 44 | `azmcp pricing get Storage (eastus)` | 3.1s |
| 45 | `azmcp pricing get Azure Container Apps (eastus)` | 1.7s |

---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources, edges, and orphans onto the 
local filesystem. Then query with standard file reads.

| Metric | Value |
|--------|-------|
| Collection time | 9.3s |
| Query time | 0.13s |
| Total time | 9.4s |
| az CLI calls (collection) | 4 |
| Filesystem commands (query) | 22 |
| Tool calls (total) | 26 |
| Tokens ingested | ~3,474 |
| Orphans found | 18 |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.0s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 2.0s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.0s |
| 4 | `az graph query -q "resources | project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind | where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 2.8s |

---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with orphans, edges, 
and pricing tables. Then query with SQL JOINs.

| Metric | Value |
|--------|-------|
| Collection time | 21.8s |
| Query time | 0.008s |
| Total time | 21.8s |
| az CLI calls (collection) | 11 |
| SQL queries (query) | 5 |
| Tool calls (total) | 16 |
| Tokens ingested | ~2,689 |
| DB size | 548.0 KB |
| Orphans found | 18 |
| Monthly waste estimate | $1841.19 |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 1.9s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 2.0s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 1.9s |
| 4 | `az graph query -q "resources | project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind | where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 2.6s |
| 5 | `azmcp pricing get API Management (eastus)` | 1.8s |
| 6 | `azmcp pricing get Cognitive Services (eastus)` | 1.8s |
| 7 | `azmcp pricing get Container Registry (eastus)` | 1.8s |
| 8 | `azmcp pricing get Key Vault (eastus)` | 1.8s |
| 9 | `azmcp pricing get Log Analytics (eastus)` | 1.7s |
| 10 | `azmcp pricing get Azure Cognitive Search (eastus)` | 2.0s |
| 11 | `azmcp pricing get Storage (eastus)` | 2.3s |

---

## Orphan Comparison

### Session A orphans (18):
- acrdeveastusdhi6n6
- acrdeveastusgoln5p
- acrdeveastusq3grjnqowando
- ai-account-fhtxfm34vs6s4
- ai-account-fhtxfm34vs6s4/ai-project-dev-eastus
- aideveastusgoln5p
- aideveastusgoln5pjtx3
- aifoundrydeveastusdhi6n6
- aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6
- apim-dev-eastus-dhi6n6
- apim-dev-eastus-goln5p
- apim-dev-eastus-q3grjnqowando
- kv-dev-eastus-dhi6n6
- kv-dev-skfkws
- search-fhtxfm34vs6s4
- srch-dev-eastus-dhi6n6
- srchdeveastusgoln5p
- stdeveastusdhi6n6

### Session B orphans (18):
- acrdeveastusdhi6n6
- acrdeveastusgoln5p
- acrdeveastusq3grjnqowando
- ai-account-fhtxfm34vs6s4
- ai-account-fhtxfm34vs6s4_ai-project-dev-eastus
- aideveastusgoln5p
- aideveastusgoln5pjtx3
- aifoundrydeveastusdhi6n6
- aifoundrydeveastusdhi6n6_proj-dev-eastus-dhi6n6
- apim-dev-eastus-dhi6n6
- apim-dev-eastus-goln5p
- apim-dev-eastus-q3grjnqowando
- kv-dev-eastus-dhi6n6
- kv-dev-skfkws
- search-fhtxfm34vs6s4
- srch-dev-eastus-dhi6n6
- srchdeveastusgoln5p
- stdeveastusdhi6n6

### Session C orphans (18):
- acrdeveastusdhi6n6
- acrdeveastusgoln5p
- acrdeveastusq3grjnqowando
- ai-account-fhtxfm34vs6s4
- ai-account-fhtxfm34vs6s4/ai-project-dev-eastus
- aideveastusgoln5p
- aideveastusgoln5pjtx3
- aifoundrydeveastusdhi6n6
- aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6
- apim-dev-eastus-dhi6n6
- apim-dev-eastus-goln5p
- apim-dev-eastus-q3grjnqowando
- kv-dev-eastus-dhi6n6
- kv-dev-skfkws
- search-fhtxfm34vs6s4
- srch-dev-eastus-dhi6n6
- srchdeveastusgoln5p
- stdeveastusdhi6n6

⚠️ **Orphan sets differ between sessions.**

---

## Key Takeaways

1. **Token reduction:** FUSE approaches ingest ~3,474–2,689 tokens vs ~286,898 for MCP
2. **az CLI call reduction:** Session A makes 45 az calls vs 4 for FUSE (one-time collection)
3. **Query-phase az calls:** Sessions B and C make **0** az calls during the query phase (all pre-computed)
4. **Time:** Session A takes 120.7s vs 9.4s/21.8s for FUSE (including collection)
5. **Cost visibility:** Only Session C surfaces the estimated **$1841.19/month** waste from orphaned resources
