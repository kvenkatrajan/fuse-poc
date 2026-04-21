"""
Azure FUSE POC — Project Azure resources onto the local filesystem.

This tool demonstrates how representing Azure resources as a filesystem
enables powerful analysis with standard tools (find, grep, diff, Get-ChildItem)
instead of service-specific API calls.

Usage:
    # Demo mode (no Azure connection needed)
    python -m azure_fuse.cli --demo --output ./azure-snapshot

    # MCP mode (uses az CLI — same APIs as Azure MCP tools)
    python -m azure_fuse.cli --mcp --subscription <sub-id-or-name> --output ./azure-snapshot

    # SDK mode (uses Azure Python SDK directly)
    python -m azure_fuse.cli --subscription <sub-id-or-name> --output ./azure-snapshot

    # From a previously saved snapshot
    python -m azure_fuse.cli --from-snapshot snapshot.json --output ./azure-snapshot

After projection, analyze with:
    # Find candidate orphaned resources
    Get-ChildItem -Recurse -Filter "_CANDIDATE_ORPHAN" | ForEach-Object { $_.Directory.FullName }

    # Check what depends on a Key Vault before deleting it
    Get-ChildItem -Path "./azure-snapshot/.../key-vaults/app-keyvault/depended-by/"

    # View the dependency graph
    Get-Content "./azure-snapshot/.../dependency-graph.md"
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .demo_data import generate_demo_resources
from .mcp_collector import collect_via_mcp
from .relationships import (
    extract_edges,
    detect_candidate_orphans,
    build_dependency_graph_mermaid,
)
from .projector import (
    project_to_filesystem,
    write_orphan_summary,
    write_dependency_graph,
)


def query_live_azure(subscription: str, resource_groups: list = None):
    """Query real Azure resources via Resource Graph SDK."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest
    except ImportError:
        print("ERROR: Azure SDK not installed. Run:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = ResourceGraphClient(credential)

    query = "resources\n| project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind"
    if resource_groups:
        rg_list = ", ".join(f"'{rg}'" for rg in resource_groups)
        query += f"\n| where resourceGroup in~ ({rg_list})"

    request = QueryRequest(
        subscriptions=[subscription],
        query=query,
    )

    scope_msg = f"resource group(s): {', '.join(resource_groups)}" if resource_groups else "entire subscription"
    print(f"Querying Azure Resource Graph ({scope_msg})")
    result = client.resources(request)
    resources = list(result.data)
    print(f"  Found {len(resources)} resources")

    for r in resources:
        if "type" in r:
            r["type"] = r["type"].lower()

    return subscription, resources


def main():
    parser = argparse.ArgumentParser(
        description="Azure FUSE POC — Project Azure resources as a local filesystem",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m azure_fuse.cli --demo --output ./azure-snapshot
  python -m azure_fuse.cli --demo --resource-groups app-prod-rg
  python -m azure_fuse.cli --mcp --subscription my-sub --resource-groups app-rg infra-rg
  python -m azure_fuse.cli --mcp --subscription my-sub --save-snapshot snapshot.json
  python -m azure_fuse.cli --from-snapshot snapshot.json --resource-groups app-rg
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true",
                       help="Use realistic mock data (no Azure connection needed)")
    group.add_argument("--mcp", action="store_true",
                       help="Collect via az CLI (same APIs as Azure MCP tools — recommended)")
    group.add_argument("--sdk", action="store_true",
                       help="Collect via Azure Python SDK (requires pip install)")
    group.add_argument("--from-snapshot", type=str, metavar="FILE",
                       help="Load from a previously saved JSON snapshot")
    parser.add_argument("--subscription", type=str,
                        help="Azure subscription ID or name (required for --mcp and --sdk)")
    parser.add_argument("--resource-groups", type=str, nargs="+", metavar="RG",
                        help="Scope to specific resource group(s). Omit for entire subscription.")
    parser.add_argument("--output", type=str, default="./azure-snapshot",
                        help="Output directory for the filesystem projection (default: ./azure-snapshot)")
    parser.add_argument("--format", type=str, choices=["filesystem", "sqlite"], default="filesystem",
                        help="Output format: 'filesystem' (directory tree) or 'sqlite' (single .db file)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove output directory before projecting")
    parser.add_argument("--session-id", type=str, default=None,
                        help="Session ID for DB isolation (default: PID). "
                             "All sub-agents sharing a session use the same ID "
                             "so they read from the same DB.")
    parser.add_argument("--save-snapshot", type=str, metavar="FILE",
                        help="Save collected resource data as JSON snapshot for reuse")

    args = parser.parse_args()

    # Validate: --mcp and --sdk require --subscription
    if (args.mcp or args.sdk) and not args.subscription:
        parser.error("--subscription is required when using --mcp or --sdk")

    output_dir = Path(args.output)

    # Clean if requested (filesystem mode only — sqlite handles its own cleanup)
    if args.format != "sqlite":
        if args.clean and output_dir.exists():
            print(f"Cleaning {output_dir}...")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # --- Collect resources ---
    if args.demo:
        print("Running in DEMO mode with mock Azure resources...\n")
        subscription, resources = generate_demo_resources()

    elif args.mcp:
        print("Running in MCP mode (az CLI — same APIs as Azure MCP tools)...\n")
        subscription, resources = collect_via_mcp(
            args.subscription,
            resource_groups=args.resource_groups,
        )

    elif args.sdk:
        subscription, resources = query_live_azure(
            args.subscription,
            resource_groups=args.resource_groups,
        )

    elif args.from_snapshot:
        snapshot_path = Path(args.from_snapshot)
        if not snapshot_path.exists():
            print(f"ERROR: Snapshot file not found: {snapshot_path}")
            sys.exit(1)
        print(f"Loading from snapshot: {snapshot_path}\n")
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        subscription = snapshot["subscription"]
        resources = snapshot["resources"]
        print(f"  Loaded {len(resources)} resources from snapshot")

    # Filter by resource groups if specified (applies to demo and snapshot modes too)
    if args.resource_groups and not args.mcp and not args.sdk:
        rg_filter = {rg.lower() for rg in args.resource_groups}
        before = len(resources)
        resources = [r for r in resources if r.get("resourceGroup", "").lower() in rg_filter]
        print(f"  Filtered to {len(resources)} resources in {len(rg_filter)} resource group(s) (from {before})")

    # Optionally save snapshot for reuse
    if args.save_snapshot:
        snapshot_path = Path(args.save_snapshot)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump({"subscription": subscription, "resources": resources}, f, indent=2)
        print(f"Saved snapshot to {snapshot_path}\n")

    # --- Analyze ---
    print("Analyzing resource relationships...")
    edges = extract_edges(resources)
    print(f"  Found {len(edges)} dependency edges")

    print("Detecting candidate orphaned resources...")
    orphans = detect_candidate_orphans(resources, edges)
    print(f"  Found {len(orphans)} candidate orphan(s)")

    print("Generating dependency graph...")
    mermaid = build_dependency_graph_mermaid(resources, edges)

    # --- Pricing enrichment (SQLite mode only) ---
    pricing = []
    if args.format == "sqlite":
        try:
            from .pricing import enrich_with_pricing
            print("\nEnriching with retail pricing (azmcp)...")
            pricing = enrich_with_pricing(resources)
        except Exception as e:
            print(f"  Pricing enrichment skipped: {e}")

    # --- Project ---
    if args.format == "sqlite":
        from .sqlite_projector import project_to_sqlite

        db_path = Path(args.output)
        if not db_path.suffix:
            # Inject session-id directory for isolation between concurrent sessions
            session_id = args.session_id or str(os.getpid())
            db_path = db_path / session_id / f"{subscription}.db"
        if args.clean and db_path.exists():
            db_path.unlink()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\nProjecting to SQLite: {db_path}")
        project_to_sqlite(db_path, subscription, resources, edges, orphans, mermaid, pricing=pricing)

        # --- Report ---
        print("\n" + "=" * 60)
        print("  PROJECTION COMPLETE (SQLite)")
        print("=" * 60)
        print(f"\n  Output: {db_path}")
        print(f"  Resources projected: {len(resources)}")
        print(f"  Dependency edges: {len(edges)}")
        print(f"  Candidate orphans: {len(orphans)}")

        print("\n  Try these queries:\n")
        print("  # Resource inventory")
        print(f'  sqlite3 "{db_path}" "SELECT name, type, location FROM resources"')
        print()
        print("  # Find orphaned resources")
        print(f'  sqlite3 "{db_path}" "SELECT r.name, r.type, o.reason FROM orphans o JOIN resources r ON o.resource_id = r.id"')
        print()
        print("  # What depends on a resource?")
        print(f'  sqlite3 "{db_path}" "SELECT source_key, relationship FROM edges WHERE target_key LIKE \'%my-resource%\'"')
        print()
        print("  # Impact analysis (what breaks if I delete X?)")
        print(f'  sqlite3 "{db_path}" "SELECT source_key, relationship FROM edges WHERE target_key LIKE \'%my-resource%\'"')
        print()
        print("  # Dependency graph")
        print(f'  sqlite3 "{db_path}" "SELECT content FROM artifacts WHERE name = \'dependency_graph_mermaid\'"')
        print()
    else:
        print(f"\nProjecting to filesystem: {output_dir}")
        sub_dir = project_to_filesystem(output_dir, subscription, resources, edges, orphans)

        write_orphan_summary(sub_dir, orphans)
        write_dependency_graph(sub_dir, mermaid)

        # --- Report ---
        print("\n" + "=" * 60)
        print("  PROJECTION COMPLETE")
        print("=" * 60)
        print(f"\n  Output: {sub_dir}")
        print(f"  Resources projected: {len(resources)}")
        print(f"  Dependency edges: {len(edges)}")
        print(f"  Candidate orphans: {len(orphans)}")

        print("\n  Try these commands:\n")
        print("  # Find orphaned resources")
        print(f'  Get-ChildItem -Path "{sub_dir}" -Recurse -Filter "_CANDIDATE_ORPHAN" |')
        print("    ForEach-Object { $_.Directory.FullName }")
        print()
        print("  # What depends on the Key Vault? (impact analysis)")
        rel = sub_dir / "resource-groups" / "platform-rg" / "key-vaults" / "app-keyvault" / "depended-by"
        print(f'  Get-ChildItem -Path "{rel}"')
        print()
        print("  # View dependency graph")
        print(f'  Get-Content "{sub_dir / "dependency-graph.md"}"')
        print()
        print("  # View orphan summary")
        print(f'  Get-Content "{sub_dir / "orphaned-resources.txt"}"')
        print()


if __name__ == "__main__":
    main()
