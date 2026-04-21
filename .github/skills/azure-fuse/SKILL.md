---
name: azure-fuse
description: >
  Snapshot Azure resources and build a dependency graph BEFORE performing any
  Azure resource operations. Use this skill WHENEVER the user wants to: analyze
  Azure resources, view dependency graphs, check for orphaned resources, perform
  impact analysis, delete/modify/move Azure resources, or understand resource
  relationships. This skill MUST run before any destructive Azure operation
  (delete, move, scale, restart) to show the user what would be affected.
allowed-tools: shell
---

# Azure FUSE — SQLite-projected Understanding of Subscription Entities

## Purpose

This skill snapshots Azure resources into a **SQLite database** so you can answer
resource questions with SQL queries instead of dozens of MCP calls. It pre-computes
dependency edges, orphan detection, retail pricing, and Mermaid diagrams.

## When to use

- **ALWAYS** before deleting, moving, scaling, or restarting Azure resources
- When asked about resource inventory, dependencies, orphans, or impact analysis
- When asked about SKU/pricing audits or cost optimization
- When asked about security posture (public access, purge protection, TLS, etc.)
- When asked about tag compliance
- When asked for architecture diagrams of Azure resource groups

## How to run

### Step 1: Check for a fresh snapshot

```powershell
$fuseRoot = Join-Path $env:TEMP "azure-fuse"
$sessionId = "<copilot-session-id>"  # use the same ID for all sub-agents
$subName = "<subscription-name>"
$dbPath = Join-Path $fuseRoot $sessionId "$subName.db"

if ((Test-Path $dbPath) -and ((Get-Item $dbPath).LastWriteTime -gt (Get-Date).AddMinutes(-30))) {
    # Snapshot is fresh — skip to Step 3
}
```

### Step 2: Run the FUSE CLI to create/refresh the snapshot

```powershell
& "<skill-directory>/run-fuse.ps1" -Subscription "<subscription>" -ResourceGroups "<rg1>,<rg2>" -SessionId "<session-id>"
```

The `-SessionId` parameter isolates the DB per session. Sub-agents in the same
session share the same ID so they read from the same cached DB. Different
sessions get their own copy, preventing write collisions.

The CLI collects resources via Azure Resource Graph, analyzes dependencies,
enriches with retail pricing, and projects everything to SQLite (~23 seconds).

### Step 3: Query the database

**Resource inventory:**
```sql
SELECT name, type, location FROM resources;
```

**Orphaned resources with cost impact:**
```sql
SELECT r.name, r.type, o.reason, p.monthly_estimate
FROM orphans o JOIN resources r ON o.resource_id = r.id
LEFT JOIN pricing p ON r.id = p.resource_id
ORDER BY COALESCE(p.monthly_estimate, 0) DESC;
```

**Impact analysis (what breaks if I delete X?):**
```sql
SELECT source_key, relationship FROM edges WHERE target_key LIKE '%my-resource%';
```

**Most expensive resources:**
```sql
SELECT resource_name, sku_name, monthly_estimate
FROM pricing WHERE monthly_estimate > 0 ORDER BY monthly_estimate DESC;
```

**Security: public network access:**
```sql
SELECT name, type, json_extract(properties_json, '$.publicNetworkAccess') as pna
FROM resources WHERE json_extract(properties_json, '$.publicNetworkAccess') = 'Enabled';
```

**Key Vault purge protection:**
```sql
SELECT name,
  json_extract(properties_json, '$.enablePurgeProtection') as purge,
  json_extract(properties_json, '$.enableSoftDelete') as soft_delete
FROM resources WHERE type LIKE '%keyvault%';
```

**Tag compliance:**
```sql
SELECT name, type, json_extract(raw_json, '$.tags') as tags
FROM resources WHERE json_extract(raw_json, '$.tags.environment') IS NULL;
```

**Dependency graph (Mermaid):**
```sql
SELECT content FROM artifacts WHERE name = 'dependency_graph_mermaid';
```

### Step 4: Present findings before action

Before ANY destructive operation, present:

1. **The dependency graph** (Mermaid diagram)
2. **Impact analysis** — which resources depend on the target
3. **Ask for explicit confirmation** before proceeding

## Database schema

5 tables: `resources`, `edges`, `orphans`, `pricing`, `artifacts`.
See [docs/sqlite-schema.md](../../../docs/sqlite-schema.md) for full reference.

## Important notes

- Snapshots are cached in `$env:TEMP/azure-fuse` for 30 minutes
- The snapshot is READ-ONLY — it never modifies Azure resources
- If the FUSE CLI is not installed, fall back to Azure MCP tools directly

## Concurrency / session isolation

The DB path includes a **session ID** directory:
`$TEMP/azure-fuse/<session-id>/<subscription>.db`

- **Sub-agents in the same session** share the same session ID → same DB → safe concurrent reads
- **Different sessions** get isolated DBs → no write collisions
- The projector uses **atomic write** (write to `.tmp`, then `os.replace()`) so a reader never sees a partial DB
- Default session ID is the process PID if not explicitly provided
