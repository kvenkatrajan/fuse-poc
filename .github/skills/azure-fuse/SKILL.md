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

# Azure FUSE — Filesystem-projected Understanding of Subscription Entities

## Purpose

This skill snapshots Azure resources so you can answer resource questions
without making dozens of MCP calls. It pre-computes dependency edges, orphan
detection, and Mermaid diagrams.

**Two output formats are supported:**
- **SQLite** (preferred) — single `.db` file, no path length issues, SQL queries
- **Filesystem** — directory tree with `.ref` files, used when SQLite projector is unavailable

The format is auto-detected: if `sqlite_projector.py` exists in the repo, SQLite is used.

## When to use

- **ALWAYS** before deleting, moving, scaling, or restarting Azure resources
- When asked about resource inventory, dependencies, orphans, or impact analysis
- When asked for architecture diagrams of Azure resource groups
- When the user says "what's in this resource group?" or similar

## How to run

### Step 1: Check for a fresh snapshot

```powershell
$fuseRoot = Join-Path $env:TEMP "azure-fuse"
$subName = "<subscription-name>" -replace '\s+', '-'

# Check SQLite first, then filesystem
$dbPath = Join-Path $fuseRoot "$subName.db"
$dirPath = Join-Path $fuseRoot $subName

if ((Test-Path $dbPath) -and ((Get-Item $dbPath).LastWriteTime -gt (Get-Date).AddMinutes(-30))) {
    $fuseFormat = "sqlite"
    $fusePath = $dbPath
    # Snapshot is fresh — skip to Step 3
} elseif ((Test-Path $dirPath) -and ((Get-Item $dirPath).LastWriteTime -gt (Get-Date).AddMinutes(-30))) {
    $fuseFormat = "filesystem"
    $fusePath = $dirPath
    # Snapshot is fresh — skip to Step 3
}
```

If a fresh snapshot exists, skip to Step 3.

### Step 2: Run the FUSE CLI to create/refresh the snapshot

```powershell
& "<skill-directory>/run-fuse.ps1" -Subscription "<subscription>" -ResourceGroups "<rg1>,<rg2>"
```

Parameters:
- `-Subscription` — Azure subscription name or ID (required)
- `-ResourceGroups` — Comma-separated list of resource group names (required)
- `-Format` — auto (default), sqlite, or filesystem

The script auto-detects the best format. Parse its output for `FUSE_FORMAT=` and
`FUSE_SNAPSHOT_PATH=` to know which format was used.

### Step 3: Read the dependency graph

**SQLite mode:**
```powershell
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); print(db.execute(""SELECT content FROM artifacts WHERE name='dependency_graph_mermaid'"").fetchone()[0]); db.close()"
```

**Filesystem mode:**
```powershell
Get-Content (Join-Path $fusePath "dependency-graph.md")
```

**Always show the dependency graph to the user** before proceeding with any
destructive operation.

### Step 4: Answer questions from the snapshot

#### SQLite mode — use these SQL queries:

**Resource inventory:**
```powershell
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); [print(f'{r[0]} | {r[1]} | {r[2]}') for r in db.execute('SELECT name, type, location FROM resources WHERE resource_group=''<rg>'' ORDER BY type, name')]; db.close()"
```

**Orphaned resources:**
```powershell
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); [print(f'{r[0]} | {r[1]} | {r[2]} | {r[3]}') for r in db.execute('SELECT r.name, r.type, o.reason, o.confidence FROM orphans o JOIN resources r ON o.resource_id=r.id')]; db.close()"
```

**Dependencies for a specific resource:**
```powershell
# What does resource X depend on?
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); [print(f'{r[0]} | {r[1]}') for r in db.execute(""SELECT target_key, relationship FROM edges WHERE source_key LIKE '%<resource-name>%'"")]; db.close()"

# What depends on resource X? (impact analysis)
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); [print(f'{r[0]} | {r[1]}') for r in db.execute(""SELECT source_key, relationship FROM edges WHERE target_key LIKE '%<resource-name>%'"")]; db.close()"
```

**All edges in a resource group:**
```powershell
python -c "import sqlite3; db=sqlite3.connect('<db-path>'); [print(f'{r[0]} -> {r[1]} [{r[2]}]') for r in db.execute(""SELECT source_key, target_key, relationship FROM edges WHERE source_key LIKE '<rg>/%' OR target_key LIKE '<rg>/%'"")]; db.close()"
```

#### Filesystem mode — use these patterns:

**Resource inventory:**
```powershell
Get-ChildItem (Join-Path $fusePath "<resource-group>") -Directory | ForEach-Object {
    $type = $_.Name
    Get-ChildItem $_.FullName -Directory | ForEach-Object {
        [PSCustomObject]@{ Type = $type; Name = $_.Name }
    }
}
```

**Orphaned resources:**
```powershell
Get-Content (Join-Path $fusePath "<resource-group>" "orphaned-resources.txt")
```

**Dependencies for a specific resource:**
```powershell
# What does resource X depend on?
Get-ChildItem -Path "<resource-dir>/deps" -Filter "*.ref" | Get-Content

# What depends on resource X?
Get-ChildItem -Path "<resource-dir>/rdeps" -Filter "*.ref" | Get-Content
```

### Step 5: Present findings before action

Before ANY destructive operation, present:

1. **The dependency graph** (Mermaid diagram)
2. **Impact analysis** — which resources depend on the target
3. **Ask for explicit confirmation** before proceeding

Example output:
```
⚠️ Impact Analysis for deleting "my-app-plan":
  - my-function-app (hosted-on my-app-plan)
  - my-web-app (hosted-on my-app-plan)

Deleting this resource will break 2 dependent resources.
Do you want to proceed?
```

## Important notes

- Snapshots are cached in `$env:TEMP/azure-fuse` for 30 minutes
- SQLite format is preferred (no Windows path length issues, faster queries)
- If the FUSE CLI is not installed, fall back to Azure MCP tools directly
- The snapshot is READ-ONLY — it never modifies Azure resources
