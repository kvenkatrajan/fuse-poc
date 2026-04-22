## Benchmark Results (Prompt 4): Security Audit

**Run date:** 2026-04-22 09:47  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> Do a security check on rg-dev-eastus. Which resources have public network access enabled? Are Key Vaults configured with purge protection? Any storage accounts allowing public blob access?

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | 80.1s | 9.6s (9.3s collect + 0.3s query) | 21.8s (21.6s collect + 0.008s query) |
| **Query-only time** | 80.1s (no pre-compute) | 0.28s | 0.008s |
| **Collection time** | N/A (live) | 9.3s | 21.6s |
| **az CLI calls** | 28 | 4 | 11 |
| **Tool calls (total)** | 28 | 39 (4 collect + 35 file reads) | 16 (11 collect + 5 SQL) |
| **Tokens ingested** | ~89,178 | ~2,242 | ~1,970 |
| **Public access found** | 19 | 19 | 19 |
| **KV without purge protection** | 2/2 | 2/2 | 2/2 |
| **Storage w/ public blob** | 0/1 | 0/1 | 0/1 |
| **Token reduction vs MCP** | baseline | ~97% less | ~98% less |
| **Time reduction vs MCP** | baseline | ~88% less | ~73% less |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources, then `az resource show` for each 
resource that could have security-relevant properties (Key Vaults, Storage, APIM, Cognitive Services, 
Container Registries, Search, Container App Environments). Parse JSON properties to extract 
`publicNetworkAccess`, `enablePurgeProtection`, `allowBlobPublicAccess`, and `networkAcls`.

| Metric | Value |
|--------|-------|
| Total time | 80.1s |
| az CLI calls | 28 |
| Tool calls (total) | 28 |
| Tokens ingested | ~89,178 |
| Public access found | 19 |
| KV without purge protection | 2/2 |
| Storage w/ public blob | 0/1 |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 3.4s |
| 2 | `az resource show: kv-dev-skfkws` | 2.8s |
| 3 | `az resource show: kv-dev-eastus-dhi6n6` | 2.9s |
| 4 | `az resource show: stdeveastusdhi6n6` | 3.2s |
| 5 | `az resource show: log-dev-skfkws` | 3.1s |
| 6 | `az resource show: appi-dev-skfkws` | 3.2s |
| 7 | `az resource show: apim-dev-eastus-dhi6n6` | 3.1s |
| 8 | `az resource show: log-dev-eastus-dhi6n6` | 3.1s |
| 9 | `az resource show: srch-dev-eastus-dhi6n6` | 2.9s |
| 10 | `az resource show: acrdeveastusdhi6n6` | 3.2s |
| 11 | `az resource show: aifoundrydeveastusdhi6n6` | 2.9s |
| 12 | `az resource show: appi-dev-eastus-dhi6n6` | 3.0s |
| 13 | `az resource show: cae-dev-eastus-dhi6n6` | 2.8s |
| 14 | `az resource show: srchdeveastusgoln5p` | 2.6s |
| 15 | `az resource show: apim-dev-eastus-goln5p` | 2.6s |
| 16 | `az resource show: logdeveastusgoln5p` | 2.6s |
| 17 | `az resource show: aideveastusgoln5p` | 2.7s |
| 18 | `az resource show: acrdeveastusgoln5p` | 2.8s |
| 19 | `az resource show: appideveastusgoln5p` | 2.9s |
| 20 | `az resource show: cae-dev-eastus-goln5p` | 2.8s |
| 21 | `az resource show: aideveastusgoln5pjtx3` | 2.8s |
| 22 | `az resource show: apim-dev-eastus-q3grjnqowando` | 2.6s |
| 23 | `az resource show: ai-account-fhtxfm34vs6s4` | 2.6s |
| 24 | `az resource show: logs-fhtxfm34vs6s4` | 2.6s |
| 25 | `az resource show: appi-fhtxfm34vs6s4` | 2.6s |
| 26 | `az resource show: search-fhtxfm34vs6s4` | 2.9s |
| 27 | `az resource show: cae-dev-eastus-q3grjnqowando` | 2.5s |
| 28 | `az resource show: acrdeveastusq3grjnqowando` | 2.7s |

---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources onto the local filesystem with 
full `properties.json` per resource. Then query with grep/file reads to extract security-relevant 
properties (`publicNetworkAccess`, `enablePurgeProtection`, `allowBlobPublicAccess`, `networkAcls`).

| Metric | Value |
|--------|-------|
| Collection time | 9.3s |
| Query time | 0.28s |
| Total time | 9.6s |
| az CLI calls (collection) | 4 |
| File reads (query) | 35 |
| Tool calls (total) | 39 |
| Tokens ingested | ~2,242 |
| Public access found | 19 |
| KV without purge protection | 2/2 |
| Storage w/ public blob | 0/1 |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.0s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 2.0s |
| 3 | `az account show --subscription cda6aeab-...` | 2.0s |
| 4 | `az graph query -q "resources \| project id, name, type, ..."` | 2.8s |

---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with full resource 
properties in `properties_json` column. Then query with SQL WHERE/LIKE clauses and JSON 
property extraction — 5 queries total.

| Metric | Value |
|--------|-------|
| Collection time | 21.6s |
| Query time | 0.008s |
| Total time | 21.8s |
| az CLI calls (collection) | 11 |
| SQL queries (query) | 5 |
| Tool calls (total) | 16 |
| Tokens ingested | ~1,970 |
| DB size | 548 KB |
| Public access found | 19 |
| KV without purge protection | 2/2 |
| Storage w/ public blob | 0/1 |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.0s |
| 2 | `az account show --subscription "githubcopilotforazure-testing"` | 1.8s |
| 3 | `az account show --subscription cda6aeab-...` | 1.9s |
| 4 | `az graph query -q "resources \| project id, name, type, ..."` | 3.0s |
| 5 | `azmcp pricing get API Management (eastus)` | 1.8s |
| 6 | `azmcp pricing get Cognitive Services (eastus)` | 1.5s |
| 7 | `azmcp pricing get Container Registry (eastus)` | 1.6s |
| 8 | `azmcp pricing get Key Vault (eastus)` | 1.7s |
| 9 | `azmcp pricing get Log Analytics (eastus)` | 1.8s |
| 10 | `azmcp pricing get Azure Cognitive Search (eastus)` | 1.9s |
| 11 | `azmcp pricing get Storage (eastus)` | 2.3s |

---

## Security Findings (All Sessions Agree)

### Resources with Public Network Access Enabled (19)

| Resource | Type | publicNetworkAccess |
|----------|------|-------------------|
| apim-dev-eastus-dhi6n6 | API Management | Enabled |
| apim-dev-eastus-goln5p | API Management | Enabled |
| apim-dev-eastus-q3grjnqowando | API Management | Enabled |
| cae-dev-eastus-dhi6n6 | Container App Environment | Enabled |
| cae-dev-eastus-goln5p | Container App Environment | Enabled |
| cae-dev-eastus-q3grjnqowando | Container App Environment | Enabled |
| ai-account-fhtxfm34vs6s4 | Cognitive Services | Enabled |
| aideveastusgoln5p | Cognitive Services | Enabled |
| aideveastusgoln5pjtx3 | Cognitive Services | Enabled |
| aifoundrydeveastusdhi6n6 | Cognitive Services | Enabled |
| acrdeveastusdhi6n6 | Container Registry | Enabled |
| acrdeveastusgoln5p | Container Registry | Enabled |
| acrdeveastusq3grjnqowando | Container Registry | Enabled |
| kv-dev-eastus-dhi6n6 | Key Vault | Enabled |
| kv-dev-skfkws | Key Vault | Enabled |
| search-fhtxfm34vs6s4 | Search Service | Enabled |
| srch-dev-eastus-dhi6n6 | Search Service | Enabled |
| srchdeveastusgoln5p | Search Service | Enabled |
| stdeveastusdhi6n6 | Storage Account | networkAcls.defaultAction=Allow |

### Key Vault Purge Protection

| Key Vault | Purge Protection | Soft Delete | Retention | RBAC |
|-----------|-----------------|-------------|-----------|------|
| kv-dev-eastus-dhi6n6 | ❌ DISABLED | ✅ Enabled | 90 days | ✅ Enabled |
| kv-dev-skfkws | ❌ DISABLED | ✅ Enabled | 7 days | ✅ Enabled |

⚠️ **Both Key Vaults lack purge protection** — deleted secrets/keys/certificates cannot be recovered if purged.

### Storage Account Security

| Storage Account | Blob Public Access | HTTPS Only | Min TLS | Network Default |
|----------------|-------------------|------------|---------|-----------------|
| stdeveastusdhi6n6 | ✅ Denied (false) | ✅ Yes | TLS1_2 | ⚠️ Allow |

✅ No storage accounts allow public blob access, but network default action is "Allow" (not restricted to VNet/IP rules).

---

## Key Takeaways

1. **Token reduction:** FUSE approaches ingest ~2,000–2,200 tokens vs ~89,178 for MCP — **97-98% reduction**
2. **az CLI call reduction:** Session A makes 28 az calls vs 4 for filesystem / 11 for SQLite (one-time collection)
3. **Query-phase az calls:** Sessions B and C make **0** az calls during the query phase (all pre-computed)
4. **Time:** Session A takes 80.1s vs 9.6s/21.6s for FUSE (including collection)
5. **Finding consistency:** All 3 sessions produce identical security findings — 19 public resources, 2/2 KVs without purge protection, 0/1 storage with public blob access
6. **Security depth:** The filesystem and SQLite approaches both capture full resource properties in a single collection pass, enabling deep security analysis without additional API calls
