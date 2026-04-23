## Benchmark Results: MCP Server vs azmcp CLI — SKU & Pricing Tier Audit

**Run date:** 2026-04-23 13:15  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`  
**azmcp version:** 3.0.0-beta.3  
**CLI parameter reference:** [Azure MCP Server tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)

**Prompt:**
> Audit the SKUs and pricing tiers for all resources in rg-dev-eastus. Which ones are using expensive tiers? Are there any cost optimization opportunities?

---

## Summary Comparison

| Metric | Session A (MCP Server) | Session B (azmcp CLI) |
|--------|------------------------|----------------------|
| **Total time** | 317.4s | 412.9s |
| **Tool/CLI calls** | 13 | 13 |
| **Total output bytes** | 133,671 | 221,625 |
| **JSON payload bytes** | 133,671 (pure JSON via SSE) | 122,927 |
| **Log overhead bytes** | 0 | 98,698 (44.5% of output) |
| **Estimated tokens (total output)** | ~33,417 | ~55,406 |
| **Estimated tokens (JSON only)** | ~33,417 | ~30,732 |
| **Resources enumerated** | 35 | 35 |

> **Key insight:** JSON payloads are comparable (~33K vs ~31K tokens). The MCP Server delivers
> **only** JSON via SSE, while the CLI mixes `info:` HTTP logging into **stdout** (not stderr),
> inflating total output to ~55K tokens — **66% more** than MCP Server. MCP Server is also
> 30% faster (317s vs 413s) due to amortized .NET startup. If an agent could strip `info:`
> lines, CLI would be ~8% cheaper in JSON tokens (~31K vs ~33K).

---

## Session A: azmcp MCP Server (HTTP/SSE transport)

**Approach:** Start `azmcp server start --mode all --transport http` as a persistent server
process, then issue MCP JSON-RPC tool calls via HTTP POST to `/message?sessionId=...` with
responses streamed back over SSE. The server stays warm across calls, avoiding repeated
.NET runtime startup costs.

| Metric | Value |
|--------|-------|
| Total time | 317.4s |
| MCP tool calls | 13 |
| Total response bytes | 133,671 |
| Estimated tokens | ~33,417 |

### MCP Server Call Log

| # | Tool | Time | Response Bytes |
|---|------|------|---------------|
| 1 | `group_resource_list` | 77.2s | 12,172 |
| 2 | `containerapps_list` | 32.2s | 1,058 |
| 3 | `appservice_webapp_get` | 16.1s | 221 |
| 4 | `foundryextensions_resource_get` (aifoundrydeveastusdhi6n6) | 22.4s | 20,747 |
| 5 | `foundryextensions_resource_get` (aideveastusgoln5p) | 23.7s | 20,747 |
| 6 | `foundryextensions_resource_get` (aideveastusgoln5pjtx3) | 22.5s | 20,747 |
| 7 | `foundryextensions_resource_get` (ai-account-fhtxfm34vs6s4) | 21.8s | 20,747 |
| 8 | `storage_account_get` (stdeveastusdhi6n6) | 34.9s | 19,746 |
| 9 | `acr_registry_list` | 32.9s | 972 |
| 10 | `monitor_workspace_list` | 16.6s | 15,588 |
| 11 | `search_service_list` | 16.6s | 474 |
| 12 | `keyvault_secret_get` (kv-dev-skfkws) | <0.1s | 226 |
| 13 | `keyvault_secret_get` (kv-dev-eastus-dhi6n6) | <0.1s | 226 |

---

## Session B: azmcp CLI (direct command-line invocations)

**Approach:** Run individual `azmcp` CLI commands for each query. Each invocation spawns a new
.NET process, pays startup cost, authenticates, makes the ARM API call, and returns JSON
mixed with `info:` log lines on **stdout**. Parameter names follow the
[official tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/).

| Metric | Value |
|--------|-------|
| Total time | 412.9s |
| CLI calls | 13 |
| Total output bytes | 221,625 |
| JSON payload bytes | 122,927 |
| Log overhead bytes | 98,698 (44.5%) |
| Estimated tokens (total) | ~55,406 |
| Estimated tokens (JSON only) | ~30,732 |

### azmcp CLI Call Log

| # | Command | Time | Total Bytes | JSON Bytes | Log Bytes |
|---|---------|------|-------------|------------|-----------|
| 1 | `azmcp group resource list --resource-group rg-dev-eastus` | 26.1s | 13,309 | 11,366 | 1,943 |
| 2 | `azmcp containerapps list --resource-group rg-dev-eastus` | 40.2s | 3,261 | 891 | 2,370 |
| 3 | `azmcp appservice webapp get --resource-group rg-dev-eastus` | 22.4s | 2,093 | 109 | 1,984 |
| 4 | `azmcp foundryextensions resource get` (aifoundrydeveastusdhi6n6) | 27.3s | 40,120 | 19,718 | 20,402 |
| 5 | `azmcp foundryextensions resource get` (aideveastusgoln5p) | 25.6s | 40,122 | 19,718 | 20,404 |
| 6 | `azmcp foundryextensions resource get` (aideveastusgoln5pjtx3) | 25.7s | 40,126 | 19,718 | 20,408 |
| 7 | `azmcp foundryextensions resource get` (ai-account-fhtxfm34vs6s4) | 25.4s | 40,127 | 19,718 | 20,409 |
| 8 | `azmcp storage account get --account stdeveastusdhi6n6` | 47.0s | 2,196 | 487 | 1,709 |
| 9 | `azmcp acr registry list --resource-group rg-dev-eastus` | 43.1s | 3,143 | 775 | 2,368 |
| 10 | `azmcp monitor workspace list` | 21.5s | 16,541 | 15,233 | 1,308 |
| 11 | `azmcp search service list` | 25.0s | 1,640 | 351 | 1,289 |
| 12 | `azmcp keyvault secret get --vault kv-dev-skfkws` | 40.9s | 9,409 | 7,382 | 2,027 |
| 13 | `azmcp keyvault secret get --vault kv-dev-eastus-dhi6n6` | 42.3s | 9,538 | 7,461 | 2,077 |

### Notes on azmcp CLI Approach

- **`info:` log lines go to stdout, not stderr:** The HTTP request/response logging is emitted
  to stdout alongside the JSON payload. `2>$null` does **not** strip them. This means an agent
  or tool consuming stdout gets ~44.5% noise by byte volume.
- **Per-call .NET startup overhead:** Each CLI invocation starts a new .NET runtime (~0.5–1s).
  CLI total time (413s) is 30% slower than MCP Server (317s).
- **Log-heavy calls:** `foundryextensions_resource_get` makes many internal ARM API calls,
  generating ~20KB of `info:` log lines per call — **more than the actual JSON payload** (~19.7KB).
- **Parameter naming differs from MCP tool names:** CLI uses `--vault` (not `--vault-name`),
  `--account` (not `--account-name`). `monitor workspace list` and `search service list` are
  subscription-scoped only — they don't accept `--resource-group`.
  See [tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/).

### Understanding the CLI Token Overhead

The CLI's total token count (~55K) is **66% higher** than MCP Server (~33K), yet the CLI's
**JSON-only** tokens (~31K) are actually **8% lower**. The entire overhead comes from .NET
`HttpClient` diagnostic log lines mixed into stdout:

```
info: System.Net.Http.HttpClient.Default.LogicalHandler[100]
      Start processing HTTP request GET https://management.azure.com/...
info: System.Net.Http.HttpClient.Default.ClientHandler[101]
      Received HTTP response headers after 372.2ms - 200
```

Every internal ARM API call the CLI makes generates these request/response log pairs on
**stdout** (not stderr), so `2>$null` / `2>$nul` cannot strip them. An agent reading CLI
stdout has no way to avoid ingesting them without parsing each line.

**Overhead breakdown by call type:**

| Call type | Calls | JSON/call | Logs/call | Log > JSON? |
|-----------|-------|-----------|-----------|-------------|
| `foundryextensions_resource_get` | 4 | ~19.7KB | ~20.4KB | ✅ **Logs exceed JSON** |
| `keyvault_secret_get` | 2 | ~7.4KB | ~2.0KB | No |
| `group_resource_list` | 1 | 11.4KB | 1.9KB | No |
| `monitor_workspace_list` | 1 | 15.2KB | 1.3KB | No |
| All other calls | 5 | <1KB | ~2KB | ✅ **Logs exceed JSON** |

The 4 `foundryextensions` calls alone contribute **~82KB of log noise** (83% of all log
overhead) because they fan out across all CognitiveServices accounts in the subscription,
making many internal ARM API calls that each generate log lines.

**Cross-prompt consistency** confirms this is a structural property of the CLI, not measurement noise:

| | JSON tokens | Log tokens | Total tokens | Log % |
|--|------------|------------|-------------|-------|
| Prompt 1 (orphan detection) | ~31K | ~25K | ~55K | 44.5% |
| Prompt 2 (dependency analysis) | ~33K | ~27K | ~61K | 43.8% |
| Prompt 3 (SKU audit) | ~31K | ~25K | ~55K | 44.5% |

The ~44% log overhead is consistent across all prompts. **The log pollution is the sole
reason CLI appears more expensive — the underlying JSON payloads are slightly smaller
than MCP Server's.** If an agent could reliably strip `info:` lines, CLI would be the
cheaper option by ~8% in pure JSON tokens.
- **Same call count:** Both approaches needed identical 13 calls.

### Response Shape Differences: MCP Server vs CLI Are Not 1:1

| Tool | MCP Server | CLI JSON | Why |
|------|-----------|----------|-----|
| `storage_account_get` | **19,746 bytes** | 487 bytes | MCP returns the full ARM payload (encryption, network rules, etc). CLI returns a curated ~9 field summary. MCP is **40× larger**. |
| `monitor_workspace_list` | 15,588 bytes | **15,233 bytes** | Both subscription-scoped. Nearly identical — both return all workspaces. |
| `foundryextensions_resource_get` | ~20,747 bytes | ~19,718 bytes | Nearly identical — full CognitiveServices account properties. |
| `keyvault_secret_get` | 226 bytes | ~7,400 bytes | Both returned **Forbidden** errors. CLI error body is 33× more verbose. See [Key Vault auth note](#key-vault-forbidden-errors). |

### Key Vault Forbidden Errors

Both MCP Server and CLI returned **Forbidden** errors on `keyvault_secret_get` — this is an
authorization issue, not a tool bug. Azure Key Vault separates management plane (ARM) from
data plane access. The identity has ARM access but lacks a data-plane RBAC role like
`Key Vault Secrets User`.

- **MCP Server:** 226-byte minimal error response
- **CLI:** ~7,400-byte verbose Forbidden JSON body (33× larger)

---

## SKU & Pricing Tier Analysis

Based on the resource data retrieved by both sessions, here is the SKU audit for
all 35 resources in `rg-dev-eastus`:

### Resources with Identifiable SKUs

| Resource | Type | SKU/Tier | Cost Level | Optimization Opportunity |
|----------|------|----------|------------|------------------------|
| stdeveastusdhi6n6 | Storage Account | Standard_LRS | 💚 Low | Already cheapest redundancy tier |
| acrdeveastusdhi6n6 | Container Registry | Basic | 💚 Low | Already lowest tier |
| acrdeveastusgoln5p | Container Registry | Basic | 💚 Low | Already lowest tier |
| acrdeveastusq3grjnqowando | Container Registry | Basic | 💚 Low | Already lowest tier |
| aifoundrydeveastusdhi6n6 | Cognitive Services | S0 | 🟡 Medium | Consider F0 (free) if usage is low |
| aideveastusgoln5p | Cognitive Services | S0 | 🟡 Medium | Consider F0 (free) if usage is low |
| aideveastusgoln5pjtx3 | Cognitive Services | S0 | 🟡 Medium | Consider F0 (free) if usage is low |
| ai-account-fhtxfm34vs6s4 | Cognitive Services | S0 | 🟡 Medium | Consider F0 (free) if usage is low |
| srch-dev-eastus-dhi6n6 | Search Service | basic | 💚 Low | Already lowest paid tier |
| srchdeveastusgoln5p | Search Service | basic | 💚 Low | Consider free tier if <3 indexes |
| search-fhtxfm34vs6s4 | Search Service | basic | 💚 Low | Consider free tier if <3 indexes |
| apim-dev-eastus-dhi6n6 | API Management | Consumption | 💚 Low | Pay-per-call, cheapest tier |
| apim-dev-eastus-goln5p | API Management | Consumption | 💚 Low | Pay-per-call, cheapest tier |
| apim-dev-eastus-q3grjnqowando | API Management | Consumption | 💚 Low | Pay-per-call, cheapest tier |
| kv-dev-skfkws | Key Vault | standard | 💚 Low | Already cheapest tier |
| kv-dev-eastus-dhi6n6 | Key Vault | standard | 💚 Low | Already cheapest tier |
| log-dev-skfkws | Log Analytics | PerGB2018 | 💚 Low | Default pay-as-you-go |
| log-dev-eastus-dhi6n6 | Log Analytics | PerGB2018 | 💚 Low | Default pay-as-you-go |
| logdeveastusgoln5p | Log Analytics | PerGB2018 | 💚 Low | Default pay-as-you-go |
| logs-fhtxfm34vs6s4 | Log Analytics | PerGB2018 | 💚 Low | Default pay-as-you-go |

### Cost Optimization Opportunities

1. **4× Cognitive Services accounts on S0 tier:** These dev accounts may not need paid S0
   tier. If usage is below F0 (free tier) limits (20 calls/min, 5K calls/month), switching
   to F0 would eliminate their cost entirely.

2. **3× Search Services on Basic tier:** For dev workloads with fewer than 3 indexes and
   50MB data, the **free** tier would suffice. Each Basic instance costs ~$75/month.

3. **18 orphaned resources (from Prompt 1):** Many of these resources (ACRs, APIM instances,
   AI accounts) are not actively consumed. Deleting unused resources would save costs
   regardless of their SKU tier.

4. **Overall assessment:** This resource group is already using relatively inexpensive tiers
   (Basic ACR, Consumption APIM, Standard KV, PerGB2018 Log Analytics). The main cost
   optimization is reducing unused resources rather than downgrading tiers.

---

## Key Takeaways

1. **JSON payload sizes are comparable:** MCP Server delivered ~33K tokens of JSON;
   CLI delivered ~31K tokens of JSON for the same 13 calls. If an agent could strip `info:`
   lines from CLI stdout, CLI would be ~8% *cheaper* in JSON tokens than MCP Server.

2. **CLI stdout pollution inflates token consumption by 66%:** The azmcp CLI mixes `info:`
   HTTP logging into stdout (not stderr). An agent consuming raw stdout ingests ~55K tokens
   vs MCP Server's ~33K. The worst offenders are the 4 `foundryextensions` calls — each
   produces ~20KB of logs alongside ~19.7KB of JSON, contributing 80KB of pure noise.

3. **Wall-clock time: MCP Server is 30% faster.** 317s vs 413s. The server amortizes
   .NET startup and authentication across all calls via a persistent process.

4. **Response shapes differ.** MCP's `storage_account_get` returns 40× more data than CLI
   (full ARM payload vs curated summary). CLI's error payloads are 33× larger than MCP's.
   These differences cancel out in aggregate.

5. **Parameter names are a pitfall.** CLI uses `--vault` (not `--vault-name`), `--account`
   (not `--account-name`). Wrong params silently produce help text. The
   [official tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)
   is essential.

6. **Accuracy parity:** Both approaches retrieved identical resource data for SKU analysis.

7. **MCP Server is better for agent integration:** clean JSON-only output, no parameter
   guessing (schemas discoverable via `tools/list`), persistent connection, and lower total
   token consumption.

### Cross-Prompt Consistency

Results are consistent with Prompt 1 (orphan detection) and Prompt 2 (dependency analysis):

| Metric | Prompt 1 | Prompt 2 | Prompt 3 |
|--------|----------|----------|----------|
| MCP Server time | 298.9s | 179.2s | 317.4s |
| CLI time | 335.8s | 278.0s | 412.9s |
| MCP tokens | ~33K | ~32K | ~33K |
| CLI JSON tokens | ~31K | ~33K | ~31K |
| CLI total tokens | ~55K | ~61K | ~55K |
| Log overhead | 44.5% | 43.8% | 44.5% |
| CLI slower by | 12% | 55% | 30% |

The ~44% log overhead and JSON parity are consistent across all three prompts. Wall-clock
time variance is primarily driven by MCP Server cold start (first call latency varies 9–79s).
