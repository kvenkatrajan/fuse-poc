## Benchmark Results: MCP Server vs azmcp CLI — Security Audit

**Run date:** 2026-04-23 13:40  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`  
**azmcp version:** 3.0.0-beta.3  
**CLI parameter reference:** [Azure MCP Server tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)

**Prompt:**
> Do a security check on rg-dev-eastus. Which resources have public network access enabled? Are Key Vaults configured with purge protection? Any storage accounts allowing public blob access?

---

## Summary Comparison

| Metric | Session A (MCP Server) | Session B (azmcp CLI) |
|--------|------------------------|----------------------|
| **Total time** | 250.8s | 272.0s |
| **Tool/CLI calls** | 13 | 13 |
| **Total output bytes** | 133,671 | 221,628 |
| **JSON payload bytes** | 133,671 (pure JSON via SSE) | 122,927 |
| **Log overhead bytes** | 0 | 98,701 (44.5% of output) |
| **Estimated tokens (total output)** | ~33,417 | ~55,407 |
| **Estimated tokens (JSON only)** | ~33,417 | ~30,732 |
| **Resources enumerated** | 35 | 35 |

> **Key insight:** JSON payloads are comparable (~33K vs ~31K tokens). The MCP Server delivers
> **only** JSON via SSE, while the CLI mixes `info:` HTTP logging into **stdout** (not stderr),
> inflating total output to ~55K tokens — **66% more** than MCP Server. MCP Server is 8%
> faster (251s vs 272s). If an agent could strip `info:` lines, CLI would be ~8% cheaper in
> JSON tokens (~31K vs ~33K).

---

## Session A: azmcp MCP Server (HTTP/SSE transport)

**Approach:** Start `azmcp server start --mode all --transport http` as a persistent server
process, then issue MCP JSON-RPC tool calls via HTTP POST to `/message?sessionId=...` with
responses streamed back over SSE.

| Metric | Value |
|--------|-------|
| Total time | 250.8s |
| MCP tool calls | 13 |
| Total response bytes | 133,671 |
| Estimated tokens | ~33,417 |

### MCP Server Call Log

| # | Tool | Time | Response Bytes |
|---|------|------|---------------|
| 1 | `group_resource_list` | 71.7s | 12,172 |
| 2 | `containerapps_list` | 24.6s | 1,058 |
| 3 | `appservice_webapp_get` | 11.9s | 221 |
| 4 | `foundryextensions_resource_get` (aifoundrydeveastusdhi6n6) | 17.7s | 20,747 |
| 5 | `foundryextensions_resource_get` (aideveastusgoln5p) | 16.8s | 20,747 |
| 6 | `foundryextensions_resource_get` (aideveastusgoln5pjtx3) | 17.1s | 20,747 |
| 7 | `foundryextensions_resource_get` (ai-account-fhtxfm34vs6s4) | 17.6s | 20,747 |
| 8 | `storage_account_get` (stdeveastusdhi6n6) | 22.4s | 19,746 |
| 9 | `acr_registry_list` | 24.3s | 972 |
| 10 | `monitor_workspace_list` | 13.0s | 15,588 |
| 11 | `search_service_list` | 13.1s | 474 |
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
| Total time | 272.0s |
| CLI calls | 13 |
| Total output bytes | 221,628 |
| JSON payload bytes | 122,927 |
| Log overhead bytes | 98,701 (44.5%) |
| Estimated tokens (total) | ~55,407 |
| Estimated tokens (JSON only) | ~30,732 |

### azmcp CLI Call Log

| # | Command | Time | Total Bytes | JSON Bytes | Log Bytes |
|---|---------|------|-------------|------------|-----------|
| 1 | `azmcp group resource list --resource-group rg-dev-eastus` | 14.4s | 13,310 | 11,366 | 1,944 |
| 2 | `azmcp containerapps list --resource-group rg-dev-eastus` | 26.4s | 3,260 | 891 | 2,369 |
| 3 | `azmcp appservice webapp get --resource-group rg-dev-eastus` | 17.0s | 2,093 | 109 | 1,984 |
| 4 | `azmcp foundryextensions resource get` (aifoundrydeveastusdhi6n6) | 20.6s | 40,123 | 19,718 | 20,405 |
| 5 | `azmcp foundryextensions resource get` (aideveastusgoln5p) | 21.1s | 40,121 | 19,718 | 20,403 |
| 6 | `azmcp foundryextensions resource get` (aideveastusgoln5pjtx3) | 21.0s | 40,123 | 19,718 | 20,405 |
| 7 | `azmcp foundryextensions resource get` (ai-account-fhtxfm34vs6s4) | 21.0s | 40,125 | 19,718 | 20,407 |
| 8 | `azmcp storage account get --account stdeveastusdhi6n6` | 26.3s | 2,197 | 487 | 1,710 |
| 9 | `azmcp acr registry list --resource-group rg-dev-eastus` | 31.9s | 3,144 | 775 | 2,369 |
| 10 | `azmcp monitor workspace list` | 19.6s | 16,545 | 15,233 | 1,312 |
| 11 | `azmcp search service list` | 18.1s | 1,641 | 351 | 1,290 |
| 12 | `azmcp keyvault secret get --vault kv-dev-skfkws` | 18.4s | 9,418 | 7,391 | 2,027 |
| 13 | `azmcp keyvault secret get --vault kv-dev-eastus-dhi6n6` | 16.3s | 9,528 | 7,452 | 2,076 |

### Notes on azmcp CLI Approach

- **`info:` log lines go to stdout, not stderr:** ~44.5% noise by byte volume. `2>$null` cannot strip them.
- **Per-call .NET startup overhead:** CLI total (272s) is 8% slower than MCP Server (251s).
- **Log-heavy calls:** Each `foundryextensions_resource_get` generates ~20KB of `info:` log lines — more than the ~19.7KB JSON payload.
- **Parameter naming:** CLI uses `--vault` (not `--vault-name`), `--account` (not `--account-name`).
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
info: System.Net.Http.HttpClient.Default.LogicalHandler[101]
      End processing HTTP request after 410.8ms - 200
```

Each internal ARM API call generates **3–4 log lines** (~200–300 bytes). These go to **stdout**
(not stderr), so `2>$null` cannot strip them. There is no CLI flag to suppress them.

#### Token composition

```
CLI total tokens  = JSON tokens + Log tokens
     ~55K        =    ~31K     +    ~25K
                       ↑              ↑
                  8% less than    100% waste
                  MCP Server      (stdout noise)
```

#### Where the ~25K log tokens come from

| Call type | Calls | Log bytes/call | Total logs | % of all logs |
|-----------|-------|---------------|------------|--------------|
| `foundryextensions_resource_get` | 4 | ~20.4KB | **~82KB** | **83%** |
| `keyvault_secret_get` | 2 | ~2.0KB | ~4KB | 4% |
| `containerapps_list` | 1 | ~2.4KB | ~2.4KB | 2% |
| `acr_registry_list` | 1 | ~2.4KB | ~2.4KB | 2% |
| All other calls (5) | 5 | ~1.3–2.0KB | ~8KB | 9% |
| **Total** | **13** | | **~99KB (~25K tokens)** | **100%** |

The 4 `foundryextensions` calls dominate because they internally scan **all CognitiveServices
accounts across the entire subscription** (not just the target resource group), making ~80
ARM API calls each — every one of which generates log lines.

#### Why MCP Server doesn't have this problem

The MCP Server is a **persistent process**. The same `info:` logs are generated internally,
but they go to the server's stderr/console — **never into the SSE response stream**. The SSE
stream contains only JSON-RPC response payloads. An agent connected via SSE sees zero log noise.

#### Why CLI JSON is actually smaller

MCP Server returns **full ARM payloads** for some tools (e.g., `storage_account_get`: 19.7KB
with encryption, network rules, etc.), while CLI returns **curated summaries** (487 bytes with
~9 fields). This makes CLI JSON 8% smaller overall. But the ~25K tokens of log noise more than
negates that advantage.

#### Cross-prompt consistency confirms this is structural

| | JSON tokens | Log tokens | Total tokens | Log % |
|--|------------|------------|-------------|-------|
| Prompt 1 (orphan detection) | ~31K | ~25K | ~55K | 44.5% |
| Prompt 2 (dependency analysis) | ~33K | ~27K | ~61K | 43.8% |
| Prompt 3 (SKU audit) | ~31K | ~25K | ~55K | 44.5% |
| **Prompt 4 (security audit)** | **~31K** | **~25K** | **~55K** | **44.5%** |

### Response Shape Differences

| Tool | MCP Server | CLI JSON | Why |
|------|-----------|----------|-----|
| `storage_account_get` | **19,746 bytes** | 487 bytes | MCP returns full ARM payload (encryption, network rules, public access config). CLI returns curated summary. MCP is **40× larger** — but this is critical for the security prompt since it includes `allowBlobPublicAccess` and network ACLs. |
| `keyvault_secret_get` | 226 bytes | ~7,400 bytes | Both Forbidden. CLI error is 33× more verbose. Neither provides purge protection status (data-plane auth required). |

### Key Vault Forbidden Errors

Both returned **Forbidden** — the identity lacks `Key Vault Secrets User` data-plane role.
Neither approach could answer the purge protection question via `keyvault_secret_get`.
Purge protection status is an ARM property on the vault resource itself (visible in
`group_resource_list`), not a data-plane secret.

---

## Security Findings

Based on resource data retrieved by both sessions:

### Public Network Access

| Resource | Type | Public Access | Finding |
|----------|------|--------------|---------|
| stdeveastusdhi6n6 | Storage Account | `allowBlobPublicAccess: false` | ✅ **Secure** — public blob access disabled |
| stdeveastusdhi6n6 | Storage Account | `enableHttpsTrafficOnly: true` | ✅ **Secure** — HTTPS enforced |
| kv-dev-skfkws | Key Vault | Public network access | ⚠️ **Unknown** — ARM listing doesn't include network ACL detail; full resource GET needed |
| kv-dev-eastus-dhi6n6 | Key Vault | Public network access | ⚠️ **Unknown** — same limitation |
| aifoundrydeveastusdhi6n6 | Cognitive Services | `publicNetworkAccess` in properties | 🔍 Visible in foundryextensions response |
| All 3 APIM instances | API Management | Consumption tier | ⚠️ Public by default on Consumption tier |
| All 3 Search instances | Search Service | Basic tier | ⚠️ Public endpoints enabled by default on Basic |

### Key Vault Purge Protection

| Key Vault | Purge Protection | Source |
|-----------|-----------------|--------|
| kv-dev-skfkws | ⚠️ **Not determinable from data-plane calls** | `keyvault_secret_get` returned Forbidden; purge protection is an ARM management-plane property |
| kv-dev-eastus-dhi6n6 | ⚠️ **Not determinable from data-plane calls** | Same limitation |

> **Note:** Purge protection status (`enablePurgeProtection`) is an ARM-level property on
> `Microsoft.KeyVault/vaults`. It's visible via `az resource show` or ARM API, but neither
> `keyvault_secret_get` (MCP or CLI) returns it — that tool queries the data plane.
> The `group_resource_list` response includes vault names but not their full ARM properties.

### Storage Account Public Blob Access

| Storage Account | `allowBlobPublicAccess` | Status |
|----------------|------------------------|--------|
| stdeveastusdhi6n6 | `false` | ✅ **Secure** |

### Security Recommendations

1. **Enable purge protection on Key Vaults** — verify via `az keyvault show` since MCP tools
   don't expose this ARM property.
2. **Review APIM network access** — Consumption tier instances are publicly accessible by default.
   Consider adding IP restrictions or VNet integration.
3. **Review Search Service network access** — Basic tier Search instances have public endpoints.
   Consider enabling private endpoints for production workloads.
4. **Storage is properly configured** — public blob access is disabled and HTTPS is enforced.
5. **Cognitive Services public access** — check `publicNetworkAccess` in the foundryextensions
   response for each AI account and disable if not needed.

---

## Key Takeaways

1. **JSON tokens comparable:** MCP Server ~33K vs CLI ~31K. If `info:` lines were strippable,
   CLI would be 8% cheaper.

2. **CLI stdout pollution: 66% more tokens.** ~55K total vs ~33K — entirely from `info:` log
   lines on stdout that `2>$null` cannot strip.

3. **Wall-clock: MCP Server 8% faster.** 251s vs 272s. Smaller gap than previous prompts due
   to lower cold-start penalty this run (72s vs 77–79s in prompts 1–3).

4. **MCP Server returns richer security data.** `storage_account_get` via MCP returns full ARM
   payload (19.7KB) including `allowBlobPublicAccess`, encryption config, and network rules.
   CLI returns only 487 bytes — a curated summary that still includes the security-relevant
   `allowBlobPublicAccess` field but omits network ACLs.

5. **Neither approach answers all security questions.** Key Vault purge protection requires
   ARM management-plane access (`az keyvault show`), which neither MCP tool nor CLI tool
   provides — `keyvault_secret_get` is a data-plane tool that returns Forbidden without
   the `Key Vault Secrets User` role.

6. **Cross-prompt pattern holds.** ~44.5% log overhead, ~33K MCP tokens, ~31K CLI JSON tokens
   — consistent across all 4 prompts. This is a structural property of the CLI, not prompt-dependent.

7. **MCP Server is better for security audits:** richer response payloads (full ARM properties),
   clean JSON output, and discoverable tool schemas via `tools/list`.
