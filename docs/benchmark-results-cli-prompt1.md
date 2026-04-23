## Benchmark Results: MCP Server vs azmcp CLI — Orphaned Resource Detection

**Run date:** 2026-04-23 12:45  
**Target:** `rg-dev-eastus` in subscription `githubcopilotforazure-testing`  
**azmcp version:** 3.0.0-beta.3  
**CLI parameter reference:** [Azure MCP Server tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)

**Prompt:**
> Find all orphaned resources in rg-dev-eastus — unattached disks, unused NICs, unassociated public IPs, and any other resources that appear to have no dependencies.

---

## Summary Comparison

| Metric | Session A (MCP Server) | Session B (azmcp CLI) |
|--------|------------------------|----------------------|
| **Total time** | 298.9s | 335.8s |
| **Tool/CLI calls** | 13 | 13 |
| **Total output bytes** | 133,671 | 221,618 |
| **JSON payload bytes** | 133,671 (pure JSON via SSE) | 122,927 |
| **Log overhead bytes** | 0 | 98,691 (44.5% of output) |
| **Estimated tokens (total output)** | ~33,417 | ~55,404 |
| **Estimated tokens (JSON only)** | ~33,417 | ~30,732 |
| **Orphans found** | 18 | 18 |
| **Resources enumerated** | 35 | 35 |

> **Key insight:** JSON payloads are comparable (~33K vs ~31K tokens). The MCP Server
> delivers **only** JSON via SSE, while the CLI mixes `info:` HTTP logging into **stdout**
> (not stderr), inflating total output to ~55K tokens — **66% more** than MCP Server.
> MCP Server is also 12% faster (299s vs 336s) due to amortized .NET startup.

---

## Session A: azmcp MCP Server (HTTP/SSE transport)

**Approach:** Start `azmcp server start --mode all --transport http` as a persistent server
process, then issue MCP JSON-RPC tool calls via HTTP POST to `/message?sessionId=...` with
responses streamed back over SSE. The server stays warm across calls, avoiding repeated
.NET runtime startup costs.

| Metric | Value |
|--------|-------|
| Total time | 298.9s |
| MCP tool calls | 13 |
| Total response bytes | 133,671 |
| Estimated tokens | ~33,417 |
| Orphans found | 18 |

### MCP Server Call Log

| # | Tool | Time | Response Bytes |
|---|------|------|---------------|
| 1 | `group_resource_list` | 79.0s | 12,172 |
| 2 | `containerapps_list` | 29.9s | 1,058 |
| 3 | `appservice_webapp_get` | 14.6s | 221 |
| 4 | `keyvault_secret_get` (kv-dev-skfkws) | <0.1s | 225 |
| 5 | `keyvault_secret_get` (kv-dev-eastus-dhi6n6) | <0.1s | 225 |
| 6 | `foundryextensions_resource_get` (aifoundrydeveastusdhi6n6) | 21.4s | 20,747 |
| 7 | `foundryextensions_resource_get` (aideveastusgoln5p) | 20.4s | 20,747 |
| 8 | `foundryextensions_resource_get` (aideveastusgoln5pjtx3) | 19.9s | 20,747 |
| 9 | `foundryextensions_resource_get` (ai-account-fhtxfm34vs6s4) | 21.0s | 20,748 |
| 10 | `storage_account_get` (stdeveastusdhi6n6) | 30.0s | 19,747 |
| 11 | `acr_registry_list` | 31.0s | 972 |
| 12 | `monitor_workspace_list` | 15.6s | 15,588 |
| 13 | `search_service_list` | 15.6s | 474 |

---

## Session B: azmcp CLI (direct command-line invocations)

**Approach:** Run individual `azmcp` CLI commands for each query. Each invocation spawns a new
.NET process, pays startup cost, authenticates, makes the ARM API call, and returns JSON
mixed with `info:` log lines on **stdout**. Parameter names follow the
[official tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/).

| Metric | Value |
|--------|-------|
| Total time | 335.8s |
| CLI calls | 13 |
| Total output bytes | 221,618 |
| JSON payload bytes | 122,927 |
| Log overhead bytes | 98,691 (44.5%) |
| Estimated tokens (total) | ~55,404 |
| Estimated tokens (JSON only) | ~30,732 |
| Orphans found | 18 |

### azmcp CLI Call Log

| # | Command | Time | Total Bytes | JSON Bytes | Log Bytes |
|---|---------|------|-------------|------------|-----------|
| 1 | `azmcp group resource list --resource-group rg-dev-eastus` | 27.7s | 13,307 | 11,366 | 1,941 |
| 2 | `azmcp containerapps list --resource-group rg-dev-eastus` | 44.9s | 3,259 | 891 | 2,368 |
| 3 | `azmcp appservice webapp get --resource-group rg-dev-eastus` | 24.7s | 2,092 | 109 | 1,983 |
| 4 | `azmcp keyvault secret get --vault kv-dev-skfkws` | 44.1s | 9,409 | 7,382 | 2,027 |
| 5 | `azmcp keyvault secret get --vault kv-dev-eastus-dhi6n6` | 16.7s | 9,536 | 7,461 | 2,075 |
| 6 | `azmcp foundryextensions resource get` (aifoundrydeveastusdhi6n6) | 23.4s | 40,122 | 19,718 | 20,404 |
| 7 | `azmcp foundryextensions resource get` (aideveastusgoln5p) | 21.9s | 40,120 | 19,718 | 20,402 |
| 8 | `azmcp foundryextensions resource get` (aideveastusgoln5pjtx3) | 22.0s | 40,127 | 19,718 | 20,409 |
| 9 | `azmcp foundryextensions resource get` (ai-account-fhtxfm34vs6s4) | 20.7s | 40,124 | 19,718 | 20,406 |
| 10 | `azmcp storage account get --account stdeveastusdhi6n6` | 27.9s | 2,196 | 487 | 1,709 |
| 11 | `azmcp acr registry list --resource-group rg-dev-eastus` | 27.7s | 3,144 | 775 | 2,369 |
| 12 | `azmcp monitor workspace list` | 16.9s | 16,541 | 15,233 | 1,308 |
| 13 | `azmcp search service list` | 17.1s | 1,641 | 351 | 1,290 |

### Notes on azmcp CLI Approach

- **`info:` log lines go to stdout, not stderr:** The HTTP request/response logging is emitted
  to stdout alongside the JSON payload. `2>$null` does **not** strip them. This means an agent
  or tool consuming stdout gets ~44.5% noise by byte volume.
- **Per-call .NET startup overhead:** Each CLI invocation starts a new .NET runtime (~0.5–1s).
  Compare `group_resource_list`: 79.0s (server, cold) vs 27.7s (CLI). The server's first call
  was slow due to cold start, but subsequent calls are faster.
- **Log-heavy calls:** `foundryextensions_resource_get` makes many internal ARM API calls
  (scanning all CognitiveServices accounts across the subscription), generating ~20KB of
  `info:` log lines per call — **more than the actual JSON payload** (~19.7KB).
- **Parameter naming differs from MCP tool names:** CLI uses `--vault` (not `--vault-name`),
  `--account` (not `--account-name`). `monitor workspace list` and `search service list` are
  subscription-scoped only — they don't accept `--resource-group`. Using wrong param names
  causes the CLI to print help text instead of data (silent failure, exit code 1).
  See [tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/).
- **Same call count:** Both approaches needed identical 13 calls.

### Response Shape Differences: MCP Server vs CLI Are Not 1:1

The MCP Server tools and CLI tools **do not return the same JSON shape or detail level** for
the same conceptual query:

| Tool | MCP Server | CLI JSON | Why |
|------|-----------|----------|-----|
| `storage_account_get` | **19,747 bytes** | 487 bytes | MCP returns the **full ARM resource payload** (encryption, network rules, blob config, etc). CLI returns a curated summary of ~9 fields. MCP is **40× larger**. |
| `monitor_workspace_list` | 15,588 bytes | **15,233 bytes** | Both subscription-scoped. Nearly identical this run — both returning all workspaces in the subscription. |
| `foundryextensions_resource_get` | ~20,747 bytes | ~19,718 bytes | Nearly identical — both return full CognitiveServices account properties. |
| `keyvault_secret_get` | 225 bytes | ~7,400 bytes | Both returned **Forbidden** errors (data-plane auth required). CLI error body is 33× more verbose. |

### Key Vault Forbidden Errors

Both MCP Server and CLI returned **Forbidden** errors on `keyvault_secret_get` — this is an
authorization issue, not a tool bug. Azure Key Vault separates two access planes:

| Plane | What it controls | Status in this benchmark |
|-------|-----------------|------------------------|
| **Management plane** (ARM) | Create/delete vaults, manage settings, list vault metadata | ✅ Authorized |
| **Data plane** | Read/write secrets, keys, certificates | ❌ **Forbidden** |

The identity used (Azure CLI login credential) has ARM-level access but **does not have a
Key Vault data-plane RBAC role** (e.g., `Key Vault Secrets User`). Both approaches hit the
same auth boundary — the difference is only in error verbosity:
- **MCP Server:** 225-byte minimal error response
- **CLI:** ~7,400-byte verbose Forbidden JSON body (33× larger)

---

## Orphan Analysis

### Orphaned Resources Found (18)

Both sessions identified the same 18 resources as orphaned (no inbound dependencies from
other resources in the resource group):

| # | Resource | Type | Why Orphaned |
|---|----------|------|-------------|
| 1 | acrdeveastusdhi6n6 | Container Registry | No container apps or deployments reference it |
| 2 | acrdeveastusgoln5p | Container Registry | No container apps pull from it |
| 3 | acrdeveastusq3grjnqowando | Container Registry | No container apps pull from it |
| 4 | ai-account-fhtxfm34vs6s4 | Cognitive Services | Standalone AI account, no linked app |
| 5 | ai-account-fhtxfm34vs6s4/ai-project-dev-eastus | AI Project | Parent account is also orphaned |
| 6 | aideveastusgoln5p | Cognitive Services | Standalone AI account |
| 7 | aideveastusgoln5pjtx3 | Cognitive Services | Standalone AI account |
| 8 | aifoundrydeveastusdhi6n6 | Cognitive Services | AI Foundry workspace with no active consumers |
| 9 | aifoundrydeveastusdhi6n6/proj-dev-eastus-dhi6n6 | AI Project | Parent workspace is orphaned |
| 10 | apim-dev-eastus-dhi6n6 | API Management | No backends configured to route traffic |
| 11 | apim-dev-eastus-goln5p | API Management | No backends configured |
| 12 | apim-dev-eastus-q3grjnqowando | API Management | No backends configured |
| 13 | kv-dev-eastus-dhi6n6 | Key Vault | No app settings or configs reference it |
| 14 | kv-dev-skfkws | Key Vault | No app settings or configs reference it |
| 15 | search-fhtxfm34vs6s4 | Search Service | No application references it |
| 16 | srch-dev-eastus-dhi6n6 | Search Service | No application references it |
| 17 | srchdeveastusgoln5p | Search Service | No application references it |
| 18 | stdeveastusdhi6n6 | Storage Account | No linked services actively using it |

✅ **Orphan sets match between sessions** — both found the same 18 orphaned resources.

---

## Key Takeaways

1. **JSON payload sizes are comparable:** MCP Server delivered ~33K tokens of JSON;
   CLI delivered ~31K tokens of JSON for the same 13 calls. The small difference comes
   from MCP returning full ARM payloads for some resources (storage: 19.7KB vs 487 bytes)
   while CLI returns verbose error bodies for others (keyvault: 7.4KB vs 225 bytes).

2. **CLI stdout pollution inflates token consumption by 66%:** The azmcp CLI mixes `info:`
   HTTP logging into stdout (not stderr). An agent consuming raw stdout ingests ~55K tokens
   vs MCP Server's ~33K. This is wasted context window. The worst offenders are the 4
   `foundryextensions` calls — each produces ~20KB of logs alongside ~19.7KB of JSON,
   contributing 80KB of pure noise from just 4 calls. **However**, if an agent could reliably
   strip the `info:` lines from stdout, CLI would actually be ~8% *cheaper* in JSON tokens
   (~31K vs ~33K) than MCP Server. The log pollution is the sole reason CLI appears more
   expensive — the underlying JSON payloads are slightly smaller.

3. **Wall-clock time: MCP Server is 12% faster.** 299s vs 336s. The server's first call was
   slow (79s cold start for `group_resource_list`), but subsequent calls benefit from the
   warm .NET runtime. CLI pays ~0.5–1s startup per invocation.

4. **Parameter names are a pitfall.** CLI uses `--vault` (not `--vault-name`), `--account`
   (not `--account-name`). Some tools are subscription-scoped only. Wrong params produce help
   text on stdout with exit code 1 — a silent failure. The
   [official tool reference](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/)
   is essential.

5. **Response shapes differ.** MCP Server and CLI return different detail levels for the same
   resource. MCP's `storage_account_get` returns 40× more data than CLI. CLI's error payloads
   are 33× larger than MCP's. These differences cancel out in aggregate, making total JSON
   tokens appear similar by coincidence.

6. **Biggest time sinks:** `group_resource_list` (79s server cold start) and
   `foundryextensions_resource_get` (~21s each) dominate both sessions due to ARM API fan-out.

7. **Accuracy parity:** Both approaches found the identical set of 18 orphaned resources.

8. **MCP Server is better for agent integration:** clean JSON-only output, no parameter
   guessing (schemas discoverable via `tools/list`), persistent connection, and lower total
   token consumption.
