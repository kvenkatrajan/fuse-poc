## Benchmark Results: MCP Server vs azmcp CLI — Tag Compliance Audit

**Run date:** 2026-04-23 14:00  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`  
**azmcp version:** 3.0.0-beta.3  
**CLI parameter reference:** [Azure MCP Server tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)

**Prompt:**
> Check tagging compliance for rg-dev-eastus. Which resources are missing environment, owner, or cost-center tags? What's the overall compliance percentage?

---

## Summary Comparison

| Metric | Session A (MCP Server) | Session B (azmcp CLI) |
|--------|------------------------|----------------------|
| **Total time** | 254.2s | 242.4s |
| **Tool/CLI calls** | 13 | 13 |
| **Total output bytes** | 133,671 | 221,631 |
| **JSON payload bytes** | 133,671 (pure JSON via SSE) | 122,936 |
| **Log overhead bytes** | 0 | 98,695 (44.5% of output) |
| **Estimated tokens (total output)** | ~33,417 | ~55,408 |
| **Estimated tokens (JSON only)** | ~33,417 | ~30,734 |
| **Resources enumerated** | 35 | 35 |

> **Key insight:** This is the first prompt where CLI wall-clock time (242s) was **faster**
> than MCP Server (254s) — the MCP Server's cold start (67s for `group_resource_list`) was
> the dominant factor. JSON payloads remain comparable (~33K vs ~31K tokens). CLI total tokens
> are still 66% higher due to `info:` log pollution on stdout.

---

## Session A: azmcp MCP Server (HTTP/SSE transport)

**Approach:** Start `azmcp server start --mode all --transport http` as a persistent server
process, then issue MCP JSON-RPC tool calls via HTTP POST to `/message?sessionId=...` with
responses streamed back over SSE.

| Metric | Value |
|--------|-------|
| Total time | 254.2s |
| MCP tool calls | 13 |
| Total response bytes | 133,671 |
| Estimated tokens | ~33,417 |

### MCP Server Call Log

| # | Tool | Time | Response Bytes |
|---|------|------|---------------|
| 1 | `group_resource_list` | 67.4s | 12,172 |
| 2 | `containerapps_list` | 24.8s | 1,058 |
| 3 | `appservice_webapp_get` | 11.4s | 221 |
| 4 | `foundryextensions_resource_get` (aifoundrydeveastusdhi6n6) | 18.3s | 20,747 |
| 5 | `foundryextensions_resource_get` (aideveastusgoln5p) | 18.6s | 20,747 |
| 6 | `foundryextensions_resource_get` (aideveastusgoln5pjtx3) | 17.9s | 20,747 |
| 7 | `foundryextensions_resource_get` (ai-account-fhtxfm34vs6s4) | 20.5s | 20,747 |
| 8 | `storage_account_get` (stdeveastusdhi6n6) | 25.1s | 19,746 |
| 9 | `acr_registry_list` | 22.9s | 972 |
| 10 | `monitor_workspace_list` | 13.6s | 15,588 |
| 11 | `search_service_list` | 13.3s | 474 |
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
| Total time | 242.4s |
| CLI calls | 13 |
| Total output bytes | 221,631 |
| JSON payload bytes | 122,936 |
| Log overhead bytes | 98,695 (44.5%) |
| Estimated tokens (total) | ~55,408 |
| Estimated tokens (JSON only) | ~30,734 |

### azmcp CLI Call Log

| # | Command | Time | Total Bytes | JSON Bytes | Log Bytes |
|---|---------|------|-------------|------------|-----------|
| 1 | `azmcp group resource list --resource-group rg-dev-eastus` | 15.4s | 13,310 | 11,366 | 1,944 |
| 2 | `azmcp containerapps list --resource-group rg-dev-eastus` | 24.0s | 3,261 | 891 | 2,370 |
| 3 | `azmcp appservice webapp get --resource-group rg-dev-eastus` | 16.7s | 2,092 | 109 | 1,983 |
| 4 | `azmcp foundryextensions resource get` (aifoundrydeveastusdhi6n6) | 19.9s | 40,120 | 19,718 | 20,402 |
| 5 | `azmcp foundryextensions resource get` (aideveastusgoln5p) | 19.8s | 40,125 | 19,718 | 20,407 |
| 6 | `azmcp foundryextensions resource get` (aideveastusgoln5pjtx3) | 19.6s | 40,123 | 19,718 | 20,405 |
| 7 | `azmcp foundryextensions resource get` (ai-account-fhtxfm34vs6s4) | 21.3s | 40,121 | 19,718 | 20,403 |
| 8 | `azmcp storage account get --account stdeveastusdhi6n6` | 23.7s | 2,197 | 487 | 1,710 |
| 9 | `azmcp acr registry list --resource-group rg-dev-eastus` | 24.8s | 3,144 | 775 | 2,369 |
| 10 | `azmcp monitor workspace list` | 15.0s | 16,542 | 15,233 | 1,309 |
| 11 | `azmcp search service list` | 14.0s | 1,641 | 351 | 1,290 |
| 12 | `azmcp keyvault secret get --vault kv-dev-skfkws` | 13.8s | 9,418 | 7,391 | 2,027 |
| 13 | `azmcp keyvault secret get --vault kv-dev-eastus-dhi6n6` | 14.3s | 9,537 | 7,461 | 2,076 |

### Notes on azmcp CLI Approach

- **`info:` log lines go to stdout, not stderr:** ~44.5% noise by byte volume. `2>$null` cannot strip them.
- **CLI was faster this run:** 242s vs 254s. The MCP Server's cold start (67s for first call) was
  the bottleneck. CLI's per-call startup (~0.5–1s × 13) totals less than the server cold start.
- **Log-heavy calls:** Each `foundryextensions_resource_get` generates ~20KB of `info:` log
  lines — more than the ~19.7KB JSON payload.
- **Parameter naming:** CLI uses `--vault` (not `--vault-name`), `--account` (not `--account-name`).
  See [tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/).

### Understanding the CLI Token Overhead

```
CLI total tokens  = JSON tokens + Log tokens
     ~55K        =    ~31K     +    ~25K
                       ↑              ↑
                  8% less than    100% waste
                  MCP Server      (stdout noise)
```

The 4 `foundryextensions` calls contribute **~82KB of log noise** (83% of all log overhead).
Cross-prompt consistency across all 5 prompts:

| | JSON tokens | Log tokens | Total tokens | Log % |
|--|------------|------------|-------------|-------|
| Prompt 1 (orphan detection) | ~31K | ~25K | ~55K | 44.5% |
| Prompt 2 (dependency analysis) | ~33K | ~27K | ~61K | 43.8% |
| Prompt 3 (SKU audit) | ~31K | ~25K | ~55K | 44.5% |
| Prompt 4 (security audit) | ~31K | ~25K | ~55K | 44.5% |
| **Prompt 5 (tag compliance)** | **~31K** | **~25K** | **~55K** | **44.5%** |

---

## Tag Compliance Analysis

### Tag Audit Results

The `group_resource_list` response includes tags for each resource. Checking for the required
tags: `environment`, `owner`, and `cost-center`.

| # | Resource | Type | `environment` | `owner` | `cost-center` | Compliant |
|---|----------|------|:---:|:---:|:---:|:---:|
| 1 | kv-dev-skfkws | Key Vault | ❌ | ❌ | ❌ | ❌ |
| 2 | log-dev-skfkws | Log Analytics | ❌ | ❌ | ❌ | ❌ |
| 3 | appi-dev-skfkws | App Insights | ❌ | ❌ | ❌ | ❌ |
| 4 | Failure Anomalies - appi-dev-skfkws | Smart Detection | ❌ | ❌ | ❌ | ❌ |
| 5 | apim-dev-eastus-dhi6n6 | API Management | ❌ | ❌ | ❌ | ❌ |
| 6 | log-dev-eastus-dhi6n6 | Log Analytics | ❌ | ❌ | ❌ | ❌ |
| 7 | srch-dev-eastus-dhi6n6 | Search Service | ❌ | ❌ | ❌ | ❌ |
| 8 | acrdeveastusdhi6n6 | Container Registry | ❌ | ❌ | ❌ | ❌ |
| 9 | aifoundrydeveastusdhi6n6 | Cognitive Services | ❌ | ❌ | ❌ | ❌ |
| 10 | stdeveastusdhi6n6 | Storage Account | ❌ | ❌ | ❌ | ❌ |
| 11 | kv-dev-eastus-dhi6n6 | Key Vault | ❌ | ❌ | ❌ | ❌ |
| 12 | appi-dev-eastus-dhi6n6 | App Insights | ❌ | ❌ | ❌ | ❌ |
| 13 | proj-dev-eastus-dhi6n6 | AI Project | ❌ | ❌ | ❌ | ❌ |
| 14 | cae-dev-eastus-dhi6n6 | Container Apps Env | ❌ | ❌ | ❌ | ❌ |
| 15 | Failure Anomalies - appi-dev-eastus-dhi6n6 | Smart Detection | ❌ | ❌ | ❌ | ❌ |
| 16 | srchdeveastusgoln5p | Search Service | ❌ | ❌ | ❌ | ❌ |
| 17 | apim-dev-eastus-goln5p | API Management | ❌ | ❌ | ❌ | ❌ |
| 18 | logdeveastusgoln5p | Log Analytics | ❌ | ❌ | ❌ | ❌ |
| 19 | aideveastusgoln5p | Cognitive Services | ❌ | ❌ | ❌ | ❌ |
| 20 | acrdeveastusgoln5p | Container Registry | ❌ | ❌ | ❌ | ❌ |
| 21 | appideveastusgoln5p | App Insights | ❌ | ❌ | ❌ | ❌ |
| 22 | cae-dev-eastus-goln5p | Container Apps Env | ❌ | ❌ | ❌ | ❌ |
| 23 | aideveastusgoln5pjtx3 | Cognitive Services | ❌ | ❌ | ❌ | ❌ |
| 24 | ca-dev-eastus-goln5p | Container App | ❌ | ❌ | ❌ | ❌ |
| 25 | Failure Anomalies - appideveastusgoln5p | Smart Detection | ❌ | ❌ | ❌ | ❌ |
| 26 | apim-dev-eastus-q3grjnqowando | API Management | ❌ | ❌ | ❌ | ❌ |
| 27 | ai-account-fhtxfm34vs6s4 | Cognitive Services | ❌ | ❌ | ❌ | ❌ |
| 28 | logs-fhtxfm34vs6s4 | Log Analytics | ❌ | ❌ | ❌ | ❌ |
| 29 | ai-project-dev-eastus | AI Project | ❌ | ❌ | ❌ | ❌ |
| 30 | appi-fhtxfm34vs6s4 | App Insights | ❌ | ❌ | ❌ | ❌ |
| 31 | search-fhtxfm34vs6s4 | Search Service | ❌ | ❌ | ❌ | ❌ |
| 32 | Failure Anomalies - appi-fhtxfm34vs6s4 | Smart Detection | ❌ | ❌ | ❌ | ❌ |
| 33 | cae-dev-eastus-q3grjnqowando | Container Apps Env | ❌ | ❌ | ❌ | ❌ |
| 34 | acrdeveastusq3grjnqowando | Container Registry | ❌ | ❌ | ❌ | ❌ |
| 35 | ragapi-dev-eastus-q3grjnqowando | Container App | ❌ | ❌ | ❌ | ❌ |

### Compliance Summary

| Tag | Resources with tag | Resources missing tag | Compliance % |
|-----|-------------------|----------------------|-------------|
| `environment` | 0 | 35 | **0%** |
| `owner` | 0 | 35 | **0%** |
| `cost-center` | 0 | 35 | **0%** |
| **Overall (all 3 tags)** | **0** | **35** | **0%** |

### Recommendations

1. **Tag compliance is 0%.** No resources in `rg-dev-eastus` have any of the three required
   tags (`environment`, `owner`, `cost-center`). This is a dev resource group that was likely
   provisioned via `azd up` without tag policies.

2. **Implement Azure Policy.** Use `Require a tag and its value` built-in policy to enforce
   tagging at creation time. This prevents future non-compliant deployments.

3. **Bulk-tag existing resources.** Use `az tag update` or ARM API to apply tags in bulk:
   ```bash
   az tag update --resource-id /subscriptions/.../resourceGroups/rg-dev-eastus \
     --operation merge --tags environment=dev owner=team cost-center=engineering
   ```

4. **Note:** `group_resource_list` was sufficient for tag compliance — the type-specific calls
   (foundryextensions, storage, etc.) were not needed for this analysis. A single-call
   approach would have been ~12K bytes / ~3K tokens for either transport.

---

## Key Takeaways

1. **JSON tokens comparable:** MCP Server ~33K vs CLI ~31K. CLI is 8% cheaper in pure JSON.

2. **CLI stdout pollution: 66% more total tokens.** ~55K vs ~33K — entirely from `info:` log
   lines on stdout that cannot be stripped with `2>$null`.

3. **Wall-clock: CLI was faster this run.** 242s vs 254s. MCP Server's cold start (67s) on
   the first call outweighed CLI's per-call startup overhead (0.5–1s × 13 ≈ 10s). This shows
   wall-clock depends on cold-start variance.

4. **Tag compliance only needed 1 call.** The `group_resource_list` response includes tags.
   The 12 additional type-specific calls were unnecessary for this prompt — both approaches
   over-fetched. A smarter agent would have stopped after call #1 (~3K tokens).

5. **Cross-prompt pattern holds.** ~44.5% log overhead and ~33K/~31K JSON parity are
   consistent across all 5 prompts — this is structural, not prompt-dependent.

6. **MCP Server is better for agent integration** despite being slightly slower this run:
   clean JSON-only output, discoverable schemas, and no log noise in the response stream.
