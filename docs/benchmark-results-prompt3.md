## Benchmark Results 4 (v2): SKU & Pricing Tier Audit

**Run date:** 2026-04-21 17:45  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> Audit the SKUs and pricing tiers for all resources in rg-dev-eastus. Which ones are using expensive tiers? Are there any cost optimization opportunities?

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | 141.9s | 11.6s | 26.7s |
| **Query-only time** | 141.9s (no pre-compute) | 0.18s | 0.14s |
| **Collection time** | N/A (live) | 11.4s | 26.6s |
| **az CLI calls** | 45 | 4 | 11 |
| **Tool calls (total)** | 45 | 8 | 16 |
| **Tokens ingested** | ~45,435 | ~10,547 | ~4,468 |
| **SKUs identified** | 20 | 0 ⚠️ | 20 |
| **Expensive tiers found** | 5 | N/A | 5 |
| **Token reduction vs MCP** | baseline | ~77% less | ~90% less |
| **Time reduction vs MCP** | baseline | ~92% less | ~81% less |
| **Monthly spend estimate** | N/A (manual) | N/A | $1,841.19 |
| **Orphan waste estimate** | N/A | N/A | $1,841.19/mo |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources, then `az resource show` for each 
resource to get full properties including SKU fields, then `azmcp pricing get` for each service 
type to map SKUs to retail pricing.

| Metric | Value |
|--------|-------|
| Total time | 141.9s |
| az CLI calls | 36 |
| azmcp pricing calls | 9 |
| Tool calls (total) | 45 |
| Tokens ingested | ~45,435 |
| SKUs identified | 20 |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 4.1s |
| 2 | `az resource show: kv-dev-skfkws` | 3.7s |
| 3 | `az resource show: log-dev-skfkws` | 4.1s |
| 4 | `az resource show: appi-dev-skfkws` | 3.8s |
| 5 | `az resource show: Failure Anomalies - appi-dev-skfkws` | 3.7s |
| 6 | `az resource show: apim-dev-eastus-dhi6n6` | 3.6s |
| 7 | `az resource show: log-dev-eastus-dhi6n6` | 3.6s |
| 8 | `az resource show: srch-dev-eastus-dhi6n6` | 3.5s |
| 9 | `az resource show: acrdeveastusdhi6n6` | 3.9s |
| 10 | `az resource show: aifoundrydeveastusdhi6n6` | 3.5s |
| 11 | `az resource show: stdeveastusdhi6n6` | 3.5s |
| 12 | `az resource show: kv-dev-eastus-dhi6n6` | 3.4s |
| 13 | `az resource show: appi-dev-eastus-dhi6n6` | 3.5s |
| 14 | `az resource show: aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6` | 3.4s |
| 15 | `az resource show: cae-dev-eastus-dhi6n6` | 4.5s |
| 16 | `az resource show: Failure Anomalies - appi-dev-eastus-dhi6n6` | 3.3s |
| 17 | `az resource show: srchdeveastusgoln5p` | 3.4s |
| 18 | `az resource show: apim-dev-eastus-goln5p` | 3.4s |
| 19 | `az resource show: logdeveastusgoln5p` | 3.6s |
| 20 | `az resource show: aideveastusgoln5p` | 3.3s |
| 21 | `az resource show: acrdeveastusgoln5p` | 3.6s |
| 22 | `az resource show: appideveastusgoln5p` | 3.3s |
| 23 | `az resource show: cae-dev-eastus-goln5p` | 4.4s |
| 24 | `az resource show: aideveastusgoln5pjtx3` | 3.6s |
| 25 | `az resource show: ca-dev-eastus-goln5p` | 3.4s |
| 26 | `az resource show: Failure Anomalies - appideveastusgoln5p` | 3.3s |
| 27 | `az resource show: apim-dev-eastus-q3grjnqowando` | 3.4s |
| 28 | `az resource show: ai-account-fhtxfm34vs6s4` | 3.5s |
| 29 | `az resource show: logs-fhtxfm34vs6s4` | 3.3s |
| 30 | `az resource show: ai-account-fhtxfm34vs6s4/ai-project-dev-eastus` | 3.5s |
| 31 | `az resource show: appi-fhtxfm34vs6s4` | 3.5s |
| 32 | `az resource show: search-fhtxfm34vs6s4` | 3.4s |
| 33 | `az resource show: Failure Anomalies - appi-fhtxfm34vs6s4` | 3.2s |
| 34 | `az resource show: cae-dev-eastus-q3grjnqowando` | 3.3s |
| 35 | `az resource show: acrdeveastusq3grjnqowando` | 3.4s |
| 36 | `az resource show: ragapi-dev-eastus-q3grjnqowando` | 4.0s |
| 37 | `azmcp pricing get API Management (eastus)` | 2.1s |
| 38 | `azmcp pricing get Azure Cognitive Search (eastus)` | 1.4s |
| 39 | `azmcp pricing get Cognitive Services (eastus)` | 1.5s |
| 40 | `azmcp pricing get Container Registry (eastus)` | 1.4s |
| 41 | `azmcp pricing get Key Vault (eastus)` | 1.3s |
| 42 | `azmcp pricing get Storage (eastus)` | 1.3s |
| 43 | `azmcp pricing get Log Analytics (eastus)` | 1.5s |
| 44 | `azmcp pricing get Application Insights (eastus)` | 1.4s |
| 45 | `azmcp pricing get Azure Container Apps (eastus)` | 1.2s |

### SKU Inventory (Session A)

| Resource | Type | SKU/Tier |
|----------|------|----------|
| kv-dev-skfkws | Key Vault | standard |
| log-dev-skfkws | Log Analytics | PerGB2018 |
| apim-dev-eastus-dhi6n6 | API Management | StandardV2 |
| log-dev-eastus-dhi6n6 | Log Analytics | PerGB2018 |
| srch-dev-eastus-dhi6n6 | Cognitive Search | basic |
| acrdeveastusdhi6n6 | Container Registry | Basic |
| aifoundrydeveastusdhi6n6 | Cognitive Services | S0 |
| stdeveastusdhi6n6 | Storage | Standard_LRS |
| kv-dev-eastus-dhi6n6 | Key Vault | standard |
| srchdeveastusgoln5p | Cognitive Search | basic |
| apim-dev-eastus-goln5p | API Management | StandardV2 |
| logdeveastusgoln5p | Log Analytics | PerGB2018 |
| aideveastusgoln5p | Cognitive Services | S0 |
| acrdeveastusgoln5p | Container Registry | Basic |
| aideveastusgoln5pjtx3 | Cognitive Services | S0 |
| apim-dev-eastus-q3grjnqowando | API Management | Developer |
| ai-account-fhtxfm34vs6s4 | Cognitive Services | S0 |
| logs-fhtxfm34vs6s4 | Log Analytics | PerGB2018 |
| search-fhtxfm34vs6s4 | Cognitive Search | standard |
| acrdeveastusq3grjnqowando | Container Registry | Basic |

---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources, edges, and orphans onto the 
local filesystem. Then query with standard file reads (Get-ChildItem, Get-Content).

| Metric | Value |
|--------|-------|
| Collection time | 11.4s |
| Query time | 0.18s |
| Total time | 11.6s |
| az CLI calls (collection) | 4 |
| Filesystem commands (query) | 4 |
| Tool calls (total) | 8 |
| Tokens ingested | ~10,547 |
| SKUs identified | 0 ⚠️ |

⚠️ **LIMITATION:** The filesystem projector writes `name`, `type`, `resourceGroup`, `location`, 
and `properties` to each `properties.json` — but **does not include the top-level `sku` field** 
from the ARM resource. This means Session B **cannot directly answer the SKU/pricing tier audit 
question** from the projected files. The agent can enumerate all 35 resources and their types from 
the directory structure, but specific SKU names (e.g., `StandardV2`, `basic`, `S0`) are not available.

**What Session B CAN determine:**
- Resource inventory: 35 resources across 12 resource types
- Orphaned resources: 18 candidates (from `_CANDIDATE_ORPHAN` markers)
- Dependency relationships: 12 edges (from `deps/` and `rdeps/` directories)

**What Session B CANNOT determine without additional az CLI calls:**
- Specific SKU names and pricing tiers
- Monthly cost estimates
- Cost optimization recommendations based on tier analysis

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.5s |
| 2 | `az account show --subscription "cda6aeab-6dec-4567-a4d8-3770583a13f0"` | 2.6s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.5s |
| 4 | `az graph query -q "resources \| project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind \| where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 3.3s |

---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with resources, edges, 
orphans, pricing, and dependency graph tables. Then query with SQL JOINs for SKU analysis.

| Metric | Value |
|--------|-------|
| Collection time | 26.6s |
| Query time | 0.14s |
| Total time | 26.7s |
| az CLI calls (collection) | 11 |
| SQL queries (query) | 5 |
| Tool calls (total) | 16 |
| Tokens ingested | ~4,468 |
| DB size | 548.0 KB |
| SKUs identified | 20 |
| Monthly spend estimate | $1,841.19 |
| Orphan waste | $1,841.19/mo |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
| 1 | `az account show` | 2.5s |
| 2 | `az account show --subscription "cda6aeab-6dec-4567-a4d8-3770583a13f0"` | 2.4s |
| 3 | `az account show --subscription cda6aeab-6dec-4567-a4d8-3770583a13f0` | 2.4s |
| 4 | `az graph query -q "resources \| project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind \| where resourceGroup in~ ('rg-dev-eastus')" --subscriptions cda6aeab-6dec-4567-a4d8-3770583a13f0 --first 1000` | 3.9s |
| 5 | `azmcp pricing get API Management (eastus)` | 2.1s |
| 6 | `azmcp pricing get Cognitive Services (eastus)` | 1.9s |
| 7 | `azmcp pricing get Container Registry (eastus)` | 2.1s |
| 8 | `azmcp pricing get Key Vault (eastus)` | 2.0s |
| 9 | `azmcp pricing get Log Analytics (eastus)` | 1.9s |
| 10 | `azmcp pricing get Azure Cognitive Search (eastus)` | 2.1s |
| 11 | `azmcp pricing get Storage (eastus)` | 2.9s |

### SQL Query Results

**Expensive Tiers (>$50/month):**

| Resource | SKU | Service | Monthly Estimate |
|----------|-----|---------|-----------------|
| apim-dev-eastus-dhi6n6 | StandardV2 | API Management | $700.00 |
| apim-dev-eastus-goln5p | StandardV2 | API Management | $700.00 |
| search-fhtxfm34vs6s4 | standard | Azure Cognitive Search | $245.28 |
| srch-dev-eastus-dhi6n6 | basic | Azure Cognitive Search | $73.73 |
| srchdeveastusgoln5p | basic | Azure Cognitive Search | $73.73 |

**All Priced Resources:**

| Resource | SKU | Service | $/mo |
|----------|-----|---------|------|
| apim-dev-eastus-dhi6n6 | StandardV2 | API Management | $700.00 |
| apim-dev-eastus-goln5p | StandardV2 | API Management | $700.00 |
| search-fhtxfm34vs6s4 | standard | Azure Cognitive Search | $245.28 |
| srch-dev-eastus-dhi6n6 | basic | Azure Cognitive Search | $73.73 |
| srchdeveastusgoln5p | basic | Azure Cognitive Search | $73.73 |
| apim-dev-eastus-q3grjnqowando | Developer | API Management | $48.03 |
| acrdeveastusdhi6n6 | Basic | Container Registry | $0.10 |
| acrdeveastusgoln5p | Basic | Container Registry | $0.10 |
| acrdeveastusq3grjnqowando | Basic | Container Registry | $0.10 |
| stdeveastusdhi6n6 | Standard_LRS | Storage | $0.06 |
| kv-dev-eastus-dhi6n6 | standard | Key Vault | $0.03 |
| kv-dev-skfkws | standard | Key Vault | $0.03 |

**Total Monthly Spend:** $1,841.19 across 12 priced resources  
**Orphan Waste:** $1,841.19/mo (all priced resources are orphans)

---

## Cost Optimization Opportunities (Session C Only)

Session C is the only approach that can answer the full prompt — identifying expensive tiers 
AND quantifying optimization opportunities — in a single pre-computed query.

| Opportunity | Resources | Potential Savings |
|-------------|-----------|-------------------|
| **Downgrade or delete APIM StandardV2** | apim-dev-eastus-dhi6n6, apim-dev-eastus-goln5p | $1,400.00/mo |
| **Delete/downgrade standard Search** | search-fhtxfm34vs6s4 | $245.28/mo |
| **Delete/downgrade basic Search** | srch-dev-eastus-dhi6n6, srchdeveastusgoln5p | $147.46/mo |
| **Downgrade APIM Developer** | apim-dev-eastus-q3grjnqowando | $48.03/mo |
| **Delete orphaned ACRs** | 3 × Basic ACR | $0.30/mo |
| **Delete orphaned KVs** | 2 × standard Key Vault | $0.06/mo |
| **Total potential savings** | 18 orphaned resources | **$1,841.19/mo** |

---

## Key Takeaways

1. **SKU audit requires structured data:** The filesystem format (Session B) does not project the ARM `sku` field, making it **unsuitable for SKU/pricing tier audits**. This is the first benchmark where the filesystem approach cannot answer the prompt.
2. **SQLite is the only complete answer:** Session C provides SKU inventory, retail pricing, monthly estimates, and cost optimization recommendations — all from 5 SQL queries in 0.14s.
3. **Token reduction:** Session C ingests ~4,468 tokens vs ~45,435 for MCP — a **90% reduction**.
4. **az CLI call reduction:** Session A makes 45 az/azmcp calls vs 11 for Session C (one-time collection).
5. **Time:** Session A takes 141.9s vs 26.7s for Session C (including collection and pricing enrichment).
6. **Cost visibility:** Only Session C surfaces the estimated **$1,841.19/month** total spend and identifies all 18 orphans as the waste pool.
7. **Expensive tiers:** Two API Management StandardV2 instances account for **76% of total spend** ($1,400/mo of $1,841/mo).
8. **Projector gap:** The filesystem projector should be updated to include `sku`, `kind`, and `tags` in `properties.json` to support SKU audit queries.
