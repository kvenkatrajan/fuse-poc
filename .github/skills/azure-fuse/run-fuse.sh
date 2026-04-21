#!/bin/bash
# Azure FUSE CLI wrapper for Linux/macOS
# Usage: ./run-fuse.sh --subscription "sub-name" --resource-groups "rg1,rg2" [--max-age 30]

set -euo pipefail

SUBSCRIPTION=""
RESOURCE_GROUPS=""
MAX_AGE_MINUTES=30

while [[ $# -gt 0 ]]; do
    case $1 in
        --subscription) SUBSCRIPTION="$2"; shift 2 ;;
        --resource-groups) RESOURCE_GROUPS="$2"; shift 2 ;;
        --max-age) MAX_AGE_MINUTES="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$SUBSCRIPTION" || -z "$RESOURCE_GROUPS" ]]; then
    echo "Usage: $0 --subscription <sub> --resource-groups <rg1,rg2>"
    exit 1
fi

FUSE_ROOT="${TMPDIR:-/tmp}/azure-fuse"
SUB_DIR_NAME=$(echo "$SUBSCRIPTION" | tr ' ' '-')
SUB_DIR="$FUSE_ROOT/$SUB_DIR_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Check if snapshot is fresh
if [[ -d "$SUB_DIR" ]]; then
    AGE_MINUTES=$(( ( $(date +%s) - $(stat -c %Y "$SUB_DIR" 2>/dev/null || stat -f %m "$SUB_DIR") ) / 60 ))
    if [[ $AGE_MINUTES -lt $MAX_AGE_MINUTES ]]; then
        echo "FUSE: Using cached snapshot (${AGE_MINUTES} min old)"
        echo "FUSE_SNAPSHOT_PATH=$SUB_DIR"
        exit 0
    else
        echo "FUSE: Snapshot is stale (${AGE_MINUTES} min old), refreshing..."
    fi
fi

# Run the FUSE CLI
echo "FUSE: Collecting resources for $RESOURCE_GROUPS in $SUBSCRIPTION..."
cd "$REPO_ROOT"
python -m azure_fuse.cli \
    --mcp \
    --subscription "$SUBSCRIPTION" \
    --resource-groups "$RESOURCE_GROUPS" \
    --output "$FUSE_ROOT" \
    --clean

# Touch directory for cache tracking
touch "$SUB_DIR" 2>/dev/null || true

echo "FUSE: Snapshot complete"
echo "FUSE_SNAPSHOT_PATH=$SUB_DIR"

# Print summary
DEP_GRAPH="$SUB_DIR/dependency-graph.md"
if [[ -f "$DEP_GRAPH" ]]; then
    echo ""
    echo "=== Dependency Graph ==="
    cat "$DEP_GRAPH"
fi

find "$FUSE_ROOT" -name "orphaned-resources.txt" -exec sh -c '
    content=$(cat "$1")
    if [ -n "$content" ]; then
        echo ""
        echo "=== Orphaned Resources ==="
        echo "$content"
    fi
' _ {} \;
