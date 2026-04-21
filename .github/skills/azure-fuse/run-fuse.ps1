#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Runs the Azure FUSE CLI to snapshot resources.
.DESCRIPTION
    Wraps `python -m azure_fuse.cli` with temp directory management,
    staleness checks, and error handling. Supports two output formats:
    - sqlite: Single .db file (recommended, avoids Windows path length issues)
    - filesystem: Directory tree with .ref files and properties.json
    Default is "auto" which picks sqlite if sqlite_projector.py exists.
.PARAMETER Subscription
    Azure subscription name or ID.
.PARAMETER ResourceGroups
    Comma-separated list of resource group names.
.PARAMETER Format
    Output format: auto, sqlite, or filesystem. Default: auto.
.PARAMETER MaxAgeMinutes
    Maximum age of a snapshot before it's considered stale. Default: 30.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Subscription,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroups,

    [ValidateSet("auto", "sqlite", "filesystem")]
    [string]$Format = "auto",

    [int]$MaxAgeMinutes = 30
)

$ErrorActionPreference = "Stop"

# Resolve paths
$fuseRoot = Join-Path $env:TEMP "azure-fuse"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." ".." "..")).Path

# Auto-detect format: prefer sqlite if the projector module exists
if ($Format -eq "auto") {
    $sqliteModule = Join-Path $repoRoot "azure_fuse" "sqlite_projector.py"
    if (Test-Path $sqliteModule) {
        $Format = "sqlite"
    } else {
        $Format = "filesystem"
    }
    Write-Host "FUSE: Auto-detected format: $Format"
}

# Normalize subscription name (used for cache paths)
$subDirName = $Subscription -replace '\s+', '-'

# Determine snapshot path based on format
if ($Format -eq "sqlite") {
    $snapshotPath = Join-Path $fuseRoot "$subDirName.db"
} else {
    $snapshotPath = Join-Path $fuseRoot $subDirName
}

# Check if snapshot is fresh
if (Test-Path $snapshotPath) {
    $age = (Get-Date) - (Get-Item $snapshotPath).LastWriteTime
    if ($age.TotalMinutes -lt $MaxAgeMinutes) {
        Write-Host "FUSE: Using cached snapshot ($([math]::Round($age.TotalMinutes, 1)) min old)"
        Write-Host "FUSE_FORMAT=$Format"
        Write-Host "FUSE_SNAPSHOT_PATH=$snapshotPath"
        exit 0
    }
    else {
        Write-Host "FUSE: Snapshot is stale ($([math]::Round($age.TotalMinutes, 1)) min old), refreshing..."
    }
}

# Ensure output directory exists
if (-not (Test-Path $fuseRoot)) {
    New-Item -ItemType Directory -Path $fuseRoot -Force | Out-Null
}

# Run the FUSE CLI
Write-Host "FUSE: Collecting resources for $ResourceGroups in $Subscription..."
$rgArgs = ($ResourceGroups -split ',') | ForEach-Object { $_.Trim() }
$rgString = $rgArgs -join ','

try {
    Push-Location $repoRoot
    if ($Format -eq "sqlite") {
        python -m azure_fuse.cli `
            --mcp `
            --subscription $Subscription `
            --resource-groups $rgString `
            --format sqlite `
            --output $snapshotPath `
            --clean
    } else {
        python -m azure_fuse.cli `
            --mcp `
            --subscription $Subscription `
            --resource-groups $rgString `
            --format filesystem `
            --output $fuseRoot `
            --clean
    }
    Pop-Location
}
catch {
    Pop-Location
    Write-Error "FUSE CLI failed: $_"
    exit 1
}

Write-Host "FUSE: Snapshot complete"
Write-Host "FUSE_FORMAT=$Format"
Write-Host "FUSE_SNAPSHOT_PATH=$snapshotPath"

# Print summary based on format
if ($Format -eq "sqlite") {
    Write-Host ""
    Write-Host "=== Summary ==="
    python -c "
import sqlite3; db = sqlite3.connect('$($snapshotPath -replace '\\','/')');c=db.cursor()
print(f'Resources: {c.execute(''SELECT COUNT(*) FROM resources'').fetchone()[0]}')
print(f'Edges: {c.execute(''SELECT COUNT(*) FROM edges'').fetchone()[0]}')
print(f'Orphans: {c.execute(''SELECT COUNT(*) FROM orphans'').fetchone()[0]}')
g=c.execute(""SELECT content FROM artifacts WHERE name='dependency_graph_mermaid'"").fetchone()
if g: print(); print('=== Dependency Graph ==='); print(g[0])
db.close()
"
} else {
    $depGraph = Join-Path $fuseRoot $subDirName "dependency-graph.md"
    if (Test-Path $depGraph) {
        Write-Host ""
        Write-Host "=== Dependency Graph ==="
        Get-Content $depGraph
    }
    $orphans = Get-ChildItem -Path $fuseRoot -Recurse -Filter "orphaned-resources.txt" -ErrorAction SilentlyContinue
    foreach ($f in $orphans) {
        $content = Get-Content $f.FullName -Raw
        if ($content -and $content.Trim().Length -gt 0) {
            Write-Host ""
            Write-Host "=== Orphaned Resources ==="
            Write-Host $content
        }
    }
}
