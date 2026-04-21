# Copilot Instructions for this Repository

## Azure Resource Operations — ALWAYS use FUSE first

**Before performing ANY Azure resource operation**, you MUST invoke the
`azure-fuse` skill to snapshot the target resource group and review the
dependency graph. This applies to:

- Deleting, moving, scaling, or restarting resources
- Analyzing resource inventory or relationships
- Checking for orphaned resources
- Impact analysis ("what depends on X?")
- Generating architecture diagrams
- Any question about what's in a resource group

### Why

The FUSE skill pre-computes dependency edges, orphan detection, and impact
analysis in a single CLI call. Without it, you would need 10-20+ individual
MCP tool calls and manual cross-referencing, which is slower, more expensive,
and misses hidden dependencies (like app settings referencing Key Vault).

### Flow

1. **Invoke `azure-fuse` skill** — this snapshots resources to `$TEMP/azure-fuse`
2. **Read the dependency graph** — always show this to the user
3. **Answer the question** from the filesystem (properties.json, .ref files, etc.)
4. **For destructive operations** — show impact analysis and ask for confirmation
5. **Only then** proceed with the actual Azure operation using MCP tools

### Do NOT skip FUSE for

- "Just delete this one resource" — still check dependencies first
- "What's in rg-XYZ?" — use FUSE instead of `group_resource_list`
- "Show me the architecture" — use FUSE's pre-generated Mermaid diagram
