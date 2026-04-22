## Benchmark Results: MCP Tools vs azmcp CLI — Orphaned Resource Detection

**Run date:** 2026-04-22 14:41  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`

**Prompt:**
> Find all orphaned resources in rg-dev-eastus — unattached disks, unused NICs, unassociated public IPs, and any other resources that appear to have no dependencies.

---

## Summary Comparison

| Metric | Session A (MCP / az CLI) | Session B (azmcp CLI) |
|--------|--------------------------|----------------------|
| **Total time** | 106.5s | 190.3s |
| **CLI calls** | 36 | 10 |
| **Tool calls (total)** | 36 | 10 |
| **Tokens ingested** | ~84,618 | ~10,070 |
| **Orphans found** | 18 | 18 |
| **Token reduction vs MCP** | baseline | ~88% less |
| **Call reduction vs MCP** | baseline | ~72% less |

---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate all 35 resources, then `az resource show` for each
resource to get full properties, then manually cross-reference to find orphans.

| Metric | Value |
|--------|-------|
| Total time | 106.5s |
| az CLI calls | 36 |
| Tool calls (total) | 36 |
| Tokens ingested | ~84,618 |
| Orphans found | 18 |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `az resource list -g rg-dev-eastus` | 3.3s |
| 2 | `az resource show: kv-dev-skfkws` | 2.6s |
| 3 | `az resource show: log-dev-skfkws` | 2.8s |
| 4 | `az resource show: appi-dev-skfkws` | 2.6s |
| 5 | `az resource show: Failure Anomalies - appi-dev-skfkws` | 2.5s |
| 6 | `az resource show: apim-dev-eastus-dhi6n6` | 2.5s |
| 7 | `az resource show: log-dev-eastus-dhi6n6` | 2.4s |
| 8 | `az resource show: srch-dev-eastus-dhi6n6` | 2.6s |
| 9 | `az resource show: acrdeveastusdhi6n6` | 2.6s |
| 10 | `az resource show: aifoundrydeveastusdhi6n6` | 2.6s |
| 11 | `az resource show: stdeveastusdhi6n6` | 2.6s |
| 12 | `az resource show: kv-dev-eastus-dhi6n6` | 2.6s |
| 13 | `az resource show: appi-dev-eastus-dhi6n6` | 2.7s |
| 14 | `az resource show: aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6` | 2.6s |
| 15 | `az resource show: cae-dev-eastus-dhi6n6` | 2.7s |
| 16 | `az resource show: Failure Anomalies - appi-dev-eastus-dhi6n6` | 2.5s |
| 17 | `az resource show: srchdeveastusgoln5p` | 2.8s |
| 18 | `az resource show: apim-dev-eastus-goln5p` | 3.6s |
| 19 | `az resource show: logdeveastusgoln5p` | 3.0s |
| 20 | `az resource show: aideveastusgoln5p` | 3.1s |
| 21 | `az resource show: acrdeveastusgoln5p` | 3.2s |
| 22 | `az resource show: appideveastusgoln5p` | 4.2s |
| 23 | `az resource show: cae-dev-eastus-goln5p` | 3.1s |
| 24 | `az resource show: aideveastusgoln5pjtx3` | 3.1s |
| 25 | `az resource show: ca-dev-eastus-goln5p` | 3.0s |
| 26 | `az resource show: Failure Anomalies - appideveastusgoln5p` | 2.7s |
| 27 | `az resource show: apim-dev-eastus-q3grjnqowando` | 2.9s |
| 28 | `az resource show: ai-account-fhtxfm34vs6s4` | 3.3s |
| 29 | `az resource show: logs-fhtxfm34vs6s4` | 2.7s |
| 30 | `az resource show: ai-account-fhtxfm34vs6s4/ai-project-dev-eastus` | 3.1s |
| 31 | `az resource show: appi-fhtxfm34vs6s4` | 2.9s |
| 32 | `az resource show: search-fhtxfm34vs6s4` | 3.5s |
| 33 | `az resource show: Failure Anomalies - appi-fhtxfm34vs6s4` | 2.6s |
| 34 | `az resource show: cae-dev-eastus-q3grjnqowando` | 2.6s |
| 35 | `az resource show: acrdeveastusq3grjnqowando` | 2.8s |
| 36 | `az resource show: ragapi-dev-eastus-q3grjnqowando` | 3.2s |

---

## Session B: azmcp CLI (Type-Specific Commands)

**Approach:** Use `azmcp group resource list` for a complete inventory, then use type-specific
azmcp commands (`acr registry list`, `containerapps list`, `foundryextensions resource get`, etc.)
to get targeted details per resource type. Cross-reference to find orphans.

| Metric | Value |
|--------|-------|
| Total time | 190.3s |
| azmcp CLI calls | 10 |
| Tool calls (total) | 10 |
| Tokens ingested | ~10,070 |
| Orphans found | 18 |

### azmcp CLI Call Log

| # | Call | Time |
|---|------|------|
| 1 | `azmcp group resource list --resource-group rg-dev-eastus` | 23.7s |
| 2 | `azmcp storage account get --account-name stdeveastusdhi6n6` | 1.6s |
| 3 | `azmcp acr registry list --resource-group rg-dev-eastus` | 44.4s |
| 4 | `azmcp containerapps list --resource-group rg-dev-eastus` | 31.0s |
| 5 | `azmcp cosmos list --resource-group rg-dev-eastus` | 1.1s |
| 6 | `azmcp foundryextensions resource get --resource-name aifoundrydeveastusdhi6n6` | 16.9s |
| 7 | `azmcp foundryextensions resource get --resource-name aideveastusgoln5p` | 16.8s |
| 8 | `azmcp foundryextensions resource get --resource-name aideveastusgoln5pjtx3` | 18.9s |
| 9 | `azmcp foundryextensions resource get --resource-name ai-account-fhtxfm34vs6s4` | 18.5s |
| 10 | `azmcp appservice webapp get --resource-group rg-dev-eastus` | 17.5s |

### Notes on azmcp CLI Approach

- **Higher per-call overhead:** Each `azmcp` invocation starts a .NET runtime (~0.5–1s startup),
  making individual calls slower than `az` CLI. The `group resource list` call alone took 23.7s
  vs 3.3s for the equivalent `az resource list`.
- **Fewer calls needed:** Type-specific list commands (e.g., `acr registry list`) return multiple
  resources at once, reducing the total call count from 36 → 10.
- **Limited type coverage:** azmcp lacks direct commands for Key Vault, Search Services,
  API Management, and Log Analytics listing — the agent must infer orphan status from the
  initial `group resource list` inventory for those types.
- **Lower token volume:** Despite verbose HTTP logging in output, the actual result payloads
  are more compact (~10K tokens vs ~85K tokens).

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

✅ **Orphan sets match between sessions** — both found the same 18 orphaned resources.

---

## Key Takeaways

1. **Token reduction:** azmcp CLI ingests ~10,070 tokens vs ~84,618 for MCP-style — an **88% reduction**
2. **Call reduction:** azmcp uses 10 CLI calls vs 36 for MCP — a **72% reduction**
3. **Wall-clock time trade-off:** azmcp is actually **slower** (190.3s vs 106.5s) due to .NET runtime startup overhead per invocation — each azmcp call pays ~0.5–1s startup cost plus higher per-call latency
4. **Type coverage gap:** azmcp lacks commands for several resource types (Key Vault, Search, APIM, Log Analytics), requiring the agent to fall back on the generic `group resource list` for those
5. **Accuracy parity:** Both approaches found the identical set of 18 orphaned resources
6. **Best fit:** MCP-style is faster for wall-clock time; azmcp CLI is better for token-constrained scenarios where context window budget matters more than latency
