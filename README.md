# Azure FUSE POC — Filesystem Projection of Azure Resources

> **What if Azure resources were files and folders?**

This POC demonstrates how projecting Azure resources onto the local filesystem
enables powerful analysis with standard tools (`find`, `grep`, `diff`, `Get-ChildItem`)
instead of service-specific API calls or MCP tool invocations.

## Quick Start

```powershell
# No Azure connection needed — uses realistic mock data
cd fuse-poc
python -m azure_fuse.cli --demo --output ./azure-snapshot

# MCP mode — queries real Azure (same APIs as Azure MCP tools)
python -m azure_fuse.cli --mcp --subscription "your-sub-id" --output ./azure-snapshot

# Save a snapshot for offline reuse / sharing
python -m azure_fuse.cli --mcp --subscription "your-sub-id" --save-snapshot snapshot.json

# Re-analyze from a saved snapshot
python -m azure_fuse.cli --from-snapshot snapshot.json --output ./azure-snapshot

# Find orphaned resources (one command!)
Get-ChildItem -Path ./azure-snapshot -Recurse -Filter "_CANDIDATE_ORPHAN" |
    ForEach-Object { $_.Directory.FullName }

# What depends on the Key Vault? (impact analysis before deleting)
Get-ChildItem "./azure-snapshot/contoso-production-001/resource-groups/platform-rg/key-vaults/app-keyvault/depended-by/"

# View dependency graph (paste into https://mermaid.live)
Get-Content "./azure-snapshot/contoso-production-001/dependency-graph.md"
```

## Why This Matters for LLMs / MCP Tools

| Scenario | MCP Tools (today) | Filesystem (this POC) | Token Savings |
|----------|-------------------|-----------------------|---------------|
| Find orphaned resources | 5-8 tool calls, ~20K tokens | `find -name _CANDIDATE_ORPHAN` → ~100 tokens | **99.5%** |
| Dependency/impact analysis | 5-6 tool calls, ~20K tokens | `ls depended-by/` → ~80 tokens | **99.6%** |
| Config comparison | 4+ tool calls, ~12K tokens | `diff prod/ staging/` → ~300 tokens | **97.5%** |

The filesystem acts as a **compression layer** — it transforms verbose JSON API responses
into concise filesystem primitives (paths, marker files, .ref files) that convey the same
information in 90-98% fewer tokens.

## Architecture

```
                  ┌──────────────────────────────┐
                  │      Collector Layer          │
                  │                               │
                  │  --demo     (mock data)       │
                  │  --mcp      (az CLI / MCP)    │
                  │  --sdk      (Python SDK)      │
                  │  --from-snapshot (JSON file)   │
                  └──────────────┬────────────────┘
                                 │ resources[]
                                 ▼
                  ┌──────────────────────────────┐
                  │      Analyzer Layer           │
                  │                               │
                  │  • Extract dependency edges   │
                  │  • Detect candidate orphans   │
                  │  • Build Mermaid graph        │
                  └──────────────┬────────────────┘
                                 │ edges[], orphans[]
                                 ▼
                  ┌──────────────────────────────┐
                  │      Projector Layer          │
                  │                               │
                  │  • Write dirs/files           │
                  │  • .ref dependency links      │
                  │  • Mermaid dependency graph   │
                  └──────────────────────────────┘
                                 │
                                 ▼
                       Local Filesystem
                  (analyzed with find/grep/diff)
```

### MCP Collection Flow

When using `--mcp`, the collector follows the same path as Azure MCP tools:

```
  --mcp --subscription <id>
           │
           ├─ Try: az graph query  (= MCP Resource Graph tool)
           │       → Single query, all resources + properties
           │       → Preferred: 1 API call for entire subscription
           │
           └─ Fallback: az resource list  (= MCP group_resource_list)
                    + az resource show    (= MCP compute/storage/etc tools)
                    → N+1 API calls
                    → Used if Resource Graph extension not installed
```

## Filesystem Structure

```
azure-snapshot/
  contoso-production-001/
    resource-groups/
      app-prod-rg/
        virtual-machines/
          web-server-01/
            properties.json
            depends-on/
              web-server-01-osdisk.ref
              web-server-01-nic.ref
        disks/
          old-staging-osdisk/           ← ORPHANED
            properties.json
            attached-to.txt             → "CANDIDATE_ORPHAN"
            _CANDIDATE_ORPHAN           ← marker file
            orphan-reason.txt           ← why it's flagged
      platform-rg/
        container-apps/
          orders-api/
            depends-on/
              prod-env.ref              → container-app-environment
              app-keyvault.ref          → key-vault (reads secrets)
        key-vaults/
          app-keyvault/
            depended-by/
              orders-api.ref            ← would break if deleted!
              admin-portal.ref          ← would break if deleted!
    orphaned-resources.txt              ← summary report
    dependency-graph.md                 ← Mermaid diagram
```

## Tracked Relationships (v1)

| Source | Target | Detection Method |
|--------|--------|-----------------|
| Disk → VM | `properties.managedBy` |
| NIC → VM | `properties.virtualMachine.id` |
| NIC → Private Endpoint | `properties.privateEndpoint` |
| Public IP → NIC/LB | `properties.ipConfiguration.id` |
| NSG → NICs/Subnets | `properties.networkInterfaces`, `.subnets` |
| Container App → Environment | `properties.managedEnvironmentId` |
| Container App → Key Vault | `properties.configuration.secrets[].keyVaultUrl` |
| App Service → Plan | `properties.serverFarmId` |
| App Service → Key Vault | `siteConfig.appSettings` containing vault URI |
| Container Env → Log Analytics | `appLogsConfiguration.logAnalyticsConfiguration` |

> **NOTE:** This is intentionally incomplete. Many relationships (managed identity
> runtime lookups, diagnostic settings, Private Link) are not captured by Resource
> Graph properties alone.

## PowerShell Analysis Helpers

```powershell
. .\analyze.ps1

# Find all candidate orphans with reasons
Find-OrphanedResources .\azure-snapshot

# Impact analysis: what breaks if I delete the Key Vault?
Get-ImpactAnalysis .\azure-snapshot "app-keyvault"

# What does orders-api depend on?
Show-DependencyChain .\azure-snapshot "orders-api"

# Tree view of all resources
Show-ResourceTree .\azure-snapshot
```

## Collection Modes

| Mode | Command | Requires | Best For |
|------|---------|----------|----------|
| **Demo** | `--demo` | Nothing | Quick demo, no Azure needed |
| **MCP** | `--mcp --subscription <id>` | `az login` | Live Azure data (recommended) |
| **SDK** | `--sdk --subscription <id>` | `pip install -r requirements.txt` + `az login` | Python SDK users |
| **Snapshot** | `--from-snapshot file.json` | Nothing | Offline reanalysis, sharing, diffing over time |

### MCP Mode (Recommended for Live Data)

```powershell
az login
python -m azure_fuse.cli --mcp --subscription "your-subscription-id" --output ./azure-snapshot
```

Uses the same Azure Resource Graph API that MCP tools call internally.
No Python Azure SDK packages needed — just `az` CLI.

### Snapshot Workflow (Diff Over Time)

```powershell
# Capture today's state
python -m azure_fuse.cli --mcp --subscription my-sub --save-snapshot snapshots/2026-04-17.json

# Next week, capture again
python -m azure_fuse.cli --mcp --subscription my-sub --save-snapshot snapshots/2026-04-24.json

# Project both and diff
python -m azure_fuse.cli --from-snapshot snapshots/2026-04-17.json --output ./snapshot-week1
python -m azure_fuse.cli --from-snapshot snapshots/2026-04-24.json --output ./snapshot-week2

# What changed?
diff -r ./snapshot-week1 ./snapshot-week2
```

## Do I Need Real FUSE?

**No — not for a POC.** This projection approach (snapshot → filesystem) proves the
same concept. Real FUSE would add:

| Feature | Snapshot (this POC) | Real FUSE |
|---------|-------------------|-----------|
| Data freshness | Point-in-time | Live (on-demand API calls) |
| Setup complexity | `python` + `pip` | FUSE driver + WinFsp/libfuse |
| Analysis capability | Same | Same |
| Write support | No | Possible but risky |
| Performance | Instant (local files) | Network latency per operation |

For orphan detection, dependency analysis, and config auditing, the snapshot
approach is actually **better** — it's faster, offline-capable, and diffable
across time (save snapshots from different dates and `diff` them).
