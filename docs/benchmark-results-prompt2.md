## Benchmark Results 3 (v2): Dependency Analysis & Key Vault Impact

**Run date:** 2026-04-21 16:54  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> What are all the dependency relationships between resources in rg-dev-eastus? If I deleted each Key Vault, what would break? Show me a dependency graph.

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | 107.6s | 10.2s | 25.1s |
| **Query-only time** | 107.6s (no pre-compute) | 0.8s | 0.49s |
| **Collection time** | N/A (live) | 9.4s | 24.6s |
| **az CLI calls** | 36 | 4 | 11 |
| **Tool calls (total)** | 42 | 8 | 16 |
| **Tokens ingested** | ~93,142 | ~2,965 | ~1,312 |
| **Edges found** | 12 | 12 | 12 |
| **Key Vault impact** | 0 dependents (both orphans) | 0 dependents (both orphans) | 0 dependents (both orphans) |
| **Token reduction vs MCP** | baseline | ~97% less | ~99% less |
| **Time reduction vs MCP** | baseline | ~91% less | ~77% less |
| **Pricing included** | No | No | Yes ($0.03/mo each KV) |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources, then `az resource show` for each 
resource to get full properties, then manually cross-reference JSON to find dependency 
relationships and Key Vault references.

| Metric | Value |
|--------|-------|
| Total time | 107.6s |
| az CLI calls | 36 |
| Tool calls (total) | 42 |
| Tokens ingested | ~93,142 |
| Edges found | 12 |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 3.5s |
| 2 | `az resource show: kv-dev-skfkws` | 2.7s |
| 3 | `az resource show: log-dev-skfkws` | 2.9s |
| 4 | `az resource show: appi-dev-skfkws` | 3.0s |
| 5 | `az resource show: Failure Anomalies - appi-dev-skfkws` | 3.2s |
| 6 | `az resource show: apim-dev-eastus-dhi6n6` | 2.8s |
| 7 | `az resource show: log-dev-eastus-dhi6n6` | 2.8s |
| 8 | `az resource show: srch-dev-eastus-dhi6n6` | 3.0s |
| 9 | `az resource show: acrdeveastusdhi6n6` | 2.8s |
| 10 | `az resource show: aifoundrydeveastusdhi6n6` | 2.8s |
| 11 | `az resource show: stdeveastusdhi6n6` | 2.7s |
| 12 | `az resource show: kv-dev-eastus-dhi6n6` | 2.8s |
| 13 | `az resource show: appi-dev-eastus-dhi6n6` | 2.9s |
| 14 | `az resource show: aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6` | 2.9s |
| 15 | `az resource show: cae-dev-eastus-dhi6n6` | 2.8s |
| 16 | `az resource show: Failure Anomalies - appi-dev-eastus-dhi6n6` | 2.7s |
| 17 | `az resource show: srchdeveastusgoln5p` | 3.8s |
| 18 | `az resource show: apim-dev-eastus-goln5p` | 2.8s |
| 19 | `az resource show: logdeveastusgoln5p` | 2.8s |
| 20 | `az resource show: aideveastusgoln5p` | 2.7s |
| 21 | `az resource show: acrdeveastusgoln5p` | 2.8s |
| 22 | `az resource show: appideveastusgoln5p` | 2.6s |
| 23 | `az resource show: cae-dev-eastus-goln5p` | 2.8s |
| 24 | `az resource show: aideveastusgoln5pjtx3` | 2.7s |
| 25 | `az resource show: ca-dev-eastus-goln5p` | 3.3s |
| 26 | `az resource show: Failure Anomalies - appideveastusgoln5p` | 2.8s |
| 27 | `az resource show: apim-dev-eastus-q3grjnqowando` | 3.1s |
| 28 | `az resource show: ai-account-fhtxfm34vs6s4` | 2.8s |
| 29 | `az resource show: logs-fhtxfm34vs6s4` | 2.6s |
| 30 | `az resource show: ai-account-fhtxfm34vs6s4/ai-project-dev-eastus` | 2.6s |
| 31 | `az resource show: appi-fhtxfm34vs6s4` | 2.8s |
| 32 | `az resource show: search-fhtxfm34vs6s4` | 2.8s |
| 33 | `az resource show: Failure Anomalies - appi-fhtxfm34vs6s4` | 2.6s |
| 34 | `az resource show: cae-dev-eastus-q3grjnqowando` | 2.7s |
| 35 | `az resource show: acrdeveastusq3grjnqowando` | 3.6s |
| 36 | `az resource show: ragapi-dev-eastus-q3grjnqowando` | 3.6s |

---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources, edges, and dependency graph onto 
the local filesystem. Then query with standard file reads (Get-Content, Get-ChildItem).

| Metric | Value |
|--------|-------|
| Collection time | 9.4s |
| Query time | 0.8s |
| Total time | 10.2s |
| az CLI calls (collection) | 4 |
| Filesystem commands (query) | 4 |
| Tool calls (total) | 8 |
| Tokens ingested | ~2,965 |
| Edges found | 12 |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.6s |
| 2 | `az account show --subscription "cda6aeab-6dec-4567-a4d8-3770583a13f0"` | 2.1s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.0s |
| 4 | `az graph query -q "resources | project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind | where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 2.7s |

---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with edges, orphans, 
pricing, and dependency graph tables. Then query with SQL JOINs.

| Metric | Value |
|--------|-------|
| Collection time | 24.6s |
| Query time | 0.49s |
| Total time | 25.1s |
| az CLI calls (collection) | 11 |
| SQL queries (query) | 5 |
| Tool calls (total) | 16 |
| Tokens ingested | ~1,312 |
| DB size | 548.0 KB |
| Edges found | 12 |
| KV monthly cost | $0.03/mo each |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.1s |
| 2 | `az account show --subscription "cda6aeab-6dec-4567-a4d8-3770583a13f0"` | 2.0s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.3s |
| 4 | `az graph query -q "resources | project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind | where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 2.9s |
| 5 | `azmcp pricing get API Management (eastus)` | 2.5s |
| 6 | `azmcp pricing get Cognitive Services (eastus)` | 2.0s |
| 7 | `azmcp pricing get Container Registry (eastus)` | 1.7s |
| 8 | `azmcp pricing get Key Vault (eastus)` | 2.2s |
| 9 | `azmcp pricing get Log Analytics (eastus)` | 1.8s |
| 10 | `azmcp pricing get Azure Cognitive Search (eastus)` | 2.3s |
| 11 | `azmcp pricing get Storage (eastus)` | 2.8s |

---

## Dependency Edges Found (All Sessions Agree: 12 edges)

| Source | Relationship | Target |
|--------|-------------|--------|
| Failure Anomalies - appi-dev-eastus-dhi6n6 | monitors | appi-dev-eastus-dhi6n6 |
| Failure Anomalies - appi-dev-skfkws | monitors | appi-dev-skfkws |
| Failure Anomalies - appi-fhtxfm34vs6s4 | monitors | appi-fhtxfm34vs6s4 |
| Failure Anomalies - appideveastusgoln5p | monitors | appideveastusgoln5p |
| appi-dev-eastus-dhi6n6 | logs-to | log-dev-eastus-dhi6n6 |
| appi-dev-skfkws | logs-to | log-dev-skfkws |
| appi-fhtxfm34vs6s4 | logs-to | logs-fhtxfm34vs6s4 |
| appideveastusgoln5p | logs-to | logdeveastusgoln5p |
| ca-dev-eastus-goln5p | hosted-in | cae-dev-eastus-goln5p |
| ragapi-dev-eastus-q3grjnqowando | hosted-in | cae-dev-eastus-q3grjnqowando |
| cae-dev-eastus-dhi6n6 | logs-to | log-dev-eastus-dhi6n6 |
| cae-dev-eastus-goln5p | logs-to | logdeveastusgoln5p |

## Key Vault Impact Analysis (All Sessions Agree)

| Key Vault | Dependents | Impact if Deleted | Status |
|-----------|-----------|-------------------|--------|
| kv-dev-eastus-dhi6n6 | 0 | Nothing would break | CANDIDATE ORPHAN |
| kv-dev-skfkws | 0 | Nothing would break | CANDIDATE ORPHAN |

Both Key Vaults are **candidate orphans** — no other resource in `rg-dev-eastus` has a detected 
dependency on either vault. Deleting them would not break any dependency edges in the graph.

⚠️ **Caveat:** This analysis is based on ARM-level property references. Application-level 
references (e.g., Key Vault URIs in app settings, environment variables, or code) are not 
captured by Resource Graph and require separate validation.

---

## Key Takeaways

1. **Token reduction:** FUSE approaches ingest ~1,312–2,965 tokens vs ~93,142 for MCP — a **97–99% reduction**
2. **az CLI call reduction:** Session A makes 36 az calls vs 4 for FUSE filesystem (one-time collection)
3. **Query-phase az calls:** Sessions B and C make **0** az calls during the query phase (all pre-computed)
4. **Time:** Session A takes 107.6s vs 10.2s/25.1s for FUSE (including collection)
5. **Pre-computed graph:** FUSE generates the full Mermaid dependency graph during collection — no manual cross-referencing needed
6. **Cost visibility:** Only Session C surfaces Key Vault pricing ($0.03/mo each)
7. **Impact analysis:** All three sessions agree — both Key Vaults are orphans with zero dependents
