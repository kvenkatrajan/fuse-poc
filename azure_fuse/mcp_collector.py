"""
MCP-based collector for Azure resources.

This module replicates what the Azure MCP tools do under the hood — it queries
Azure Resource Graph (or falls back to az resource list) via the az CLI to
collect resources with their full properties.

Collection strategy:
  1. Try `az graph query` (Resource Graph — single call, all resources + properties)
  2. Fall back to `az resource list` + `az resource show` per resource type

This is equivalent to calling these MCP tools:
  - azure-mcp-group_list          → az group list
  - azure-mcp-group_resource_list → az resource list -g <rg>
  - azure-mcp-compute (disk_get)  → az resource show (for disk properties)
  - azure-mcp-compute (vm_get)    → az resource show (for VM properties)
"""

import json
import subprocess
import sys
import time
from typing import List, Tuple, Optional

# Resource types that need full properties for relationship analysis
DETAIL_TYPES = {
    "microsoft.compute/disks",                       # managedBy
    "microsoft.compute/virtualmachines",              # storageProfile, networkProfile
    "microsoft.network/networkinterfaces",            # virtualMachine, privateEndpoint
    "microsoft.network/publicipaddresses",            # ipConfiguration
    "microsoft.network/networksecuritygroups",        # networkInterfaces, subnets
    "microsoft.app/containerapps",                    # managedEnvironmentId, secrets
    "microsoft.app/managedenvironments",              # appLogsConfiguration
    "microsoft.web/sites",                            # serverFarmId, siteConfig
    "microsoft.web/serverfarms",                      # sku
    "microsoft.keyvault/vaults",                      # vaultUri
    "microsoft.storage/storageaccounts",              # primaryEndpoints
    "microsoft.operationalinsights/workspaces",       # customerId
}


def _run_az(cmd: str) -> Optional[dict]:
    """Run an az CLI command and return parsed JSON, or None on failure."""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=120,
        )
        elapsed = time.perf_counter() - start
        # Emit structured log line for benchmark instrumentation
        short_cmd = cmd.split(" -o ")[0] if " -o " in cmd else cmd[:100]
        print(f"  [AZ_CALL] {short_cmd} | {elapsed:.1f}s")
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                print(f"  az CLI error: {stderr[:200]}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start
        print(f"  [AZ_CALL] {cmd[:100]} | {elapsed:.1f}s | TIMEOUT")
        print("  az CLI command timed out", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("  Failed to parse az CLI JSON output", file=sys.stderr)
        return None


def _check_az_cli() -> bool:
    """Verify az CLI is installed and logged in."""
    result = _run_az("az account show -o json")
    if not result:
        print("ERROR: Azure CLI not available or not logged in.")
        print("  Install: https://aka.ms/installazurecli")
        print("  Login:   az login")
        return False
    return True


def _resolve_subscription(subscription: str) -> Optional[str]:
    """Resolve subscription name to ID if needed, and validate access."""
    # Try as-is first (could be an ID or name)
    result = _run_az(f'az account show --subscription "{subscription}" -o json')
    if result:
        sub_id = result.get("id", subscription)
        sub_name = result.get("name", subscription)
        print(f"  Subscription: {sub_name} ({sub_id})")
        return sub_id

    print(f"ERROR: Cannot access subscription '{subscription}'")
    print("  Run 'az account list -o table' to see available subscriptions.")
    return None


def collect_via_resource_graph(subscription_id: str, resource_groups: List[str] = None) -> Optional[List[dict]]:
    """
    Collect resources via Azure Resource Graph (single query).
    This is equivalent to what the MCP Resource Graph tools do.
    Optionally scoped to specific resource groups.
    """
    scope_msg = f"resource group(s): {', '.join(resource_groups)}" if resource_groups else "entire subscription"
    print(f"  Strategy: Azure Resource Graph ({scope_msg})")

    query = "resources | project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind"
    if resource_groups:
        rg_list = ", ".join(f"'{rg}'" for rg in resource_groups)
        query += f" | where resourceGroup in~ ({rg_list})"

    cmd = f'az graph query -q "{query}" --subscriptions {subscription_id} --first 1000 -o json'

    result = _run_az(cmd)
    if not result:
        return None

    resources = result.get("data", [])
    if not resources:
        print("  WARNING: Resource Graph returned 0 resources")
        return None

    # Normalize type to lowercase
    for r in resources:
        if "type" in r:
            r["type"] = r["type"].lower()

    print(f"  Collected {len(resources)} resources via Resource Graph")
    return resources


def collect_via_resource_list(subscription_id: str, resource_groups: List[str] = None) -> Optional[List[dict]]:
    """
    Fallback: collect resources via az resource list + individual detail fetches.
    This is equivalent to calling multiple MCP tools:
      - azure-mcp-group_list
      - azure-mcp-group_resource_list (per RG)
      - azure-mcp-compute/storage/etc (for details)
    Optionally scoped to specific resource groups.
    """
    scope_msg = f"resource group(s): {', '.join(resource_groups)}" if resource_groups else "entire subscription"
    print(f"  Strategy: az resource list + detail fetches ({scope_msg})")

    all_resources = []

    if resource_groups:
        # Scoped: query each RG individually (fewer API calls)
        for rg in resource_groups:
            print(f"  Listing resources in {rg}...")
            rg_resources = _run_az(
                f'az resource list --subscription {subscription_id} -g "{rg}" -o json'
            )
            if rg_resources:
                all_resources.extend(rg_resources)
                print(f"    Found {len(rg_resources)} resources")
            else:
                print(f"    WARNING: No resources or RG not found: {rg}")
    else:
        # Full subscription
        print("  Listing all resources in subscription...")
        all_resources = _run_az(f'az resource list --subscription {subscription_id} -o json')
        if not all_resources:
            return None

    print(f"  Found {len(all_resources)} resources total")

    # Step 2: Fetch full properties for types we need
    detail_count = 0
    for r in all_resources:
        rtype = r.get("type", "").lower()
        r["type"] = rtype

        if rtype in DETAIL_TYPES:
            resource_id = r.get("id", "")
            if not resource_id:
                continue

            print(f"  Fetching details: {r.get('name', '?')} ({rtype})...", end="")
            detail = _run_az(f'az resource show --ids "{resource_id}" -o json')
            if detail and "properties" in detail:
                r["properties"] = detail["properties"]
                detail_count += 1
                print(" OK")
            else:
                print(" SKIPPED")

    print(f"  Fetched detailed properties for {detail_count} resources")

    # Step 3: Fetch app settings for web apps / function apps
    # This discovers storage, monitoring, identity, and Key Vault edges
    # that aren't visible in the resource properties alone.
    # Equivalent to: MCP appservice tool + az webapp config appsettings list
    _enrich_with_app_settings(all_resources, subscription_id)

    return all_resources


# Resource types that have fetchable app settings
_APP_SETTINGS_TYPES = {
    "microsoft.web/sites",          # App Service and Function Apps
}


def _enrich_with_app_settings(resources: List[dict], subscription_id: str):
    """
    Fetch app settings for web apps / function apps and merge them into
    the resource's properties.siteConfig.appSettings.

    App settings often contain connection strings and URIs that reveal
    hidden dependencies:
      - AzureWebJobsStorage        → Storage Account
      - APPINSIGHTS_INSTRUMENTATIONKEY / APPLICATIONINSIGHTS_CONNECTION_STRING → App Insights
      - WEBSITE_CONTENTAZUREFILECONNECTIONSTRING → Storage Account
      - KeyVaultUri / *_VAULT_*    → Key Vault
      - IDENTITY_ENDPOINT          → Managed Identity
      - *_ENDPOINT / *_CONNECTION_STRING → Various services
    """
    app_count = 0
    apps = [r for r in resources if r.get("type", "").lower() in _APP_SETTINGS_TYPES]

    if not apps:
        return

    print(f"\n  Fetching app settings for {len(apps)} web/function app(s)...")

    for r in apps:
        name = r.get("name", "")
        rg = r.get("resourceGroup", "")
        if not name or not rg:
            continue

        print(f"    {name}...", end="")
        settings = _run_az(
            f'az webapp config appsettings list'
            f' --name "{name}" --resource-group "{rg}"'
            f' --subscription {subscription_id} -o json'
        )

        if settings and isinstance(settings, list):
            # Merge into properties.siteConfig.appSettings
            props = r.setdefault("properties", {})
            site_config = props.setdefault("siteConfig", {})
            # Convert from [{name, value, slotSetting}] format
            site_config["appSettings"] = [
                {"name": s.get("name", ""), "value": s.get("value", "")}
                for s in settings
            ]
            app_count += 1
            print(f" OK ({len(settings)} settings)")
        else:
            print(" SKIPPED")

    print(f"  Enriched {app_count} app(s) with app settings")


def collect_via_mcp(subscription: str, resource_groups: List[str] = None) -> Tuple[str, List[dict]]:
    """
    Main entry point: collect Azure resources using MCP-equivalent az CLI calls.

    Tries Resource Graph first (fast, single call), falls back to resource list
    + per-resource detail calls. Optionally scoped to specific resource groups.

    Returns (subscription_name, resources_list).
    """
    scope_msg = f" (scoped to: {', '.join(resource_groups)})" if resource_groups else ""
    print(f"Collecting resources via MCP-equivalent az CLI calls{scope_msg}...\n")

    # Verify az CLI
    if not _check_az_cli():
        sys.exit(1)

    # Resolve subscription
    sub_id = _resolve_subscription(subscription)
    if not sub_id:
        sys.exit(1)

    # Get subscription display name
    acct = _run_az(f'az account show --subscription {sub_id} -o json')
    sub_name = acct.get("name", sub_id) if acct else sub_id

    # Try Resource Graph first (what MCP tools use internally)
    print("\n  Attempting Resource Graph query...")
    resources = collect_via_resource_graph(sub_id, resource_groups=resource_groups)

    # Fall back to resource list + detail fetches
    if not resources:
        print("  Resource Graph unavailable, falling back to resource list...")
        print("  (Install extension: az extension add --name resource-graph)\n")
        resources = collect_via_resource_list(sub_id, resource_groups=resource_groups)

    if not resources:
        print("ERROR: Failed to collect any resources.")
        sys.exit(1)

    # Enrich web/function apps with app settings (discovers hidden edges)
    # Resource Graph doesn't include appSettings, so we always fetch them
    _enrich_with_app_settings(resources, sub_id)

    return sub_name, resources
