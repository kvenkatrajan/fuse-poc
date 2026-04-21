<#
.SYNOPSIS
    PowerShell helpers for analyzing the Azure FUSE filesystem projection.

.DESCRIPTION
    After running the projection (python -m azure_fuse.cli --demo --output ./azure-snapshot),
    use these functions to analyze the results with familiar PowerShell commands.

.EXAMPLE
    . .\analyze.ps1                          # Dot-source to load functions
    Find-OrphanedResources .\azure-snapshot  # Find candidate orphans
    Get-ImpactAnalysis .\azure-snapshot "app-keyvault"  # What depends on this?
    Show-DependencyChain .\azure-snapshot "orders-api"  # What does this depend on?
#>

function Find-OrphanedResources {
    <#
    .SYNOPSIS Find all candidate orphaned resources in the projection.
    .PARAMETER Path Root of the azure-snapshot directory.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    Write-Host "`n  CANDIDATE ORPHANED RESOURCES" -ForegroundColor Red
    Write-Host "  $('=' * 50)" -ForegroundColor Red

    $orphans = Get-ChildItem -Path $Path -Recurse -Filter "_CANDIDATE_ORPHAN" -ErrorAction SilentlyContinue

    if (-not $orphans) {
        Write-Host "  No candidate orphans found.`n" -ForegroundColor Green
        return
    }

    foreach ($marker in $orphans) {
        $resDir = $marker.Directory
        $reasonFile = Join-Path $resDir.FullName "orphan-reason.txt"
        $propsFile = Join-Path $resDir.FullName "properties.json"

        # Extract resource info from path
        $parts = $resDir.FullName -split [regex]::Escape([IO.Path]::DirectorySeparatorChar)
        $resName = $parts[-1]
        $resType = $parts[-2]

        Write-Host "`n  $resName" -ForegroundColor Yellow -NoNewline
        Write-Host " ($resType)" -ForegroundColor DarkGray

        if (Test-Path $reasonFile) {
            Get-Content $reasonFile | ForEach-Object {
                Write-Host "    $_" -ForegroundColor Gray
            }
        }
    }
    Write-Host "`n  Total: $($orphans.Count) candidate orphan(s)`n" -ForegroundColor Red
}


function Get-ImpactAnalysis {
    <#
    .SYNOPSIS Check what depends on a specific resource (what breaks if you delete it).
    .PARAMETER Path Root of the azure-snapshot directory.
    .PARAMETER ResourceName Name of the resource to check.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ResourceName
    )

    Write-Host "`n  IMPACT ANALYSIS: $ResourceName" -ForegroundColor Cyan
    Write-Host "  $('=' * 50)" -ForegroundColor Cyan

    # Find the resource directory
    $resDirs = Get-ChildItem -Path $Path -Recurse -Directory -Filter $ResourceName -ErrorAction SilentlyContinue

    if (-not $resDirs) {
        Write-Host "  Resource '$ResourceName' not found in projection.`n" -ForegroundColor Red
        return
    }

    foreach ($resDir in $resDirs) {
        $dependedByDir = Join-Path $resDir.FullName "depended-by"

        if (-not (Test-Path $dependedByDir)) {
            Write-Host "`n  No resources depend on $ResourceName — safe to delete.`n" -ForegroundColor Green
            return
        }

        $refs = Get-ChildItem -Path $dependedByDir -Filter "*.ref" -ErrorAction SilentlyContinue

        if (-not $refs) {
            Write-Host "`n  No resources depend on $ResourceName — safe to delete.`n" -ForegroundColor Green
            return
        }

        Write-Host "`n  WARNING: $($refs.Count) resource(s) depend on $ResourceName!" -ForegroundColor Red
        Write-Host "  Deleting it would impact:`n" -ForegroundColor Red

        foreach ($ref in $refs) {
            $content = Get-Content $ref.FullName
            $depName = $ref.BaseName
            $relationship = ($content | Where-Object { $_ -match "^relationship:" }) -replace "relationship:\s*", ""

            Write-Host "    - $depName" -ForegroundColor Yellow -NoNewline
            Write-Host " ($relationship)" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}


function Show-DependencyChain {
    <#
    .SYNOPSIS Show what a specific resource depends on.
    .PARAMETER Path Root of the azure-snapshot directory.
    .PARAMETER ResourceName Name of the resource to inspect.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ResourceName
    )

    Write-Host "`n  DEPENDENCIES: $ResourceName" -ForegroundColor Cyan
    Write-Host "  $('=' * 50)" -ForegroundColor Cyan

    $resDirs = Get-ChildItem -Path $Path -Recurse -Directory -Filter $ResourceName -ErrorAction SilentlyContinue

    if (-not $resDirs) {
        Write-Host "  Resource '$ResourceName' not found.`n" -ForegroundColor Red
        return
    }

    foreach ($resDir in $resDirs) {
        $dependsOnDir = Join-Path $resDir.FullName "depends-on"

        if (-not (Test-Path $dependsOnDir)) {
            Write-Host "`n  $ResourceName has no dependencies.`n" -ForegroundColor Green
            return
        }

        $refs = Get-ChildItem -Path $dependsOnDir -Filter "*.ref" -ErrorAction SilentlyContinue

        if (-not $refs) {
            Write-Host "`n  $ResourceName has no dependencies.`n" -ForegroundColor Green
            return
        }

        Write-Host "`n  $ResourceName depends on:`n" -ForegroundColor Yellow

        foreach ($ref in $refs) {
            $content = Get-Content $ref.FullName
            $targetName = $ref.BaseName
            $relationship = ($content | Where-Object { $_ -match "^relationship:" }) -replace "relationship:\s*", ""

            Write-Host "    -> $targetName" -ForegroundColor Green -NoNewline
            Write-Host " ($relationship)" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}


function Show-ResourceTree {
    <#
    .SYNOPSIS Display a tree view of the projected filesystem.
    .PARAMETER Path Root of the azure-snapshot directory.
    .PARAMETER Depth Maximum depth to display (default: 4).
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [int]$Depth = 4
    )

    Write-Host "`n  AZURE RESOURCE TREE" -ForegroundColor Cyan
    Write-Host "  $('=' * 50)`n" -ForegroundColor Cyan

    Get-ChildItem -Path $Path -Recurse -Depth $Depth -Directory |
        Where-Object { $_.Name -notin @("depends-on", "depended-by") } |
        ForEach-Object {
            $indent = "  " * ($_.FullName.Split([IO.Path]::DirectorySeparatorChar).Count - $Path.Split([IO.Path]::DirectorySeparatorChar).Count)
            $icon = if (Test-Path (Join-Path $_.FullName "_CANDIDATE_ORPHAN")) { "[ORPHAN] " } else { "" }
            $color = if ($icon) { "Red" } else { "White" }
            Write-Host "$indent$icon$($_.Name)/" -ForegroundColor $color
        }
    Write-Host ""
}
