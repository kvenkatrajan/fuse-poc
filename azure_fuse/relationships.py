"""
Relationship analyzer for Azure resources.

Extracts dependency edges and detects candidate orphaned resources
based on known, queryable relationships.

SUPPORTED RELATIONSHIPS (v2):
  - Disk → VM              (properties.managedBy)
  - NIC → VM               (properties.virtualMachine)
  - NIC → Private Endpoint (properties.privateEndpoint)
  - Public IP → NIC or LB  (properties.ipConfiguration)
  - NSG → NICs / Subnets   (properties.networkInterfaces, .subnets)
  - Container App → Environment  (properties.managedEnvironmentId)
  - Container App → Key Vault    (properties.configuration.secrets[].keyVaultUrl)
  - App Service → App Service Plan (properties.serverFarmId)
  - App Service → Key Vault         (appSettings containing vault URIs)
  - App Service → Storage Account   (appSettings: AzureWebJobsStorage, connection strings,
                                      or plain account names like STORAGE_ACCOUNT_NAME)
  - App Service → App Insights      (appSettings: APPINSIGHTS_*, APPLICATIONINSIGHTS_*)
  - App Service → Managed Identity   (appSettings: AZURE_CLIENT_ID matched to identity clientId)
  - App Insights → Log Analytics     (properties.WorkspaceResourceId)
  - Smart Detector Alert → scope     (properties.scope[] resource references)
  - Container App Env → Log Analytics (properties.appLogsConfiguration)

NOTE: This is intentionally incomplete. Many relationships (diagnostic settings,
private endpoints, etc.) are not captured.
"""

import re
from typing import Dict, List, Tuple, Optional

# Maps azure type → friendly directory name
RESOURCE_TYPE_MAP = {
    "microsoft.compute/virtualmachines": "virtual-machines",
    "microsoft.compute/disks": "disks",
    "microsoft.network/networkinterfaces": "network-interfaces",
    "microsoft.network/publicipaddresses": "public-ip-addresses",
    "microsoft.network/networksecuritygroups": "network-security-groups",
    "microsoft.web/serverfarms": "app-service-plans",
    "microsoft.web/sites": "app-services",
    "microsoft.app/containerapps": "container-apps",
    "microsoft.app/managedenvironments": "container-app-environments",
    "microsoft.keyvault/vaults": "key-vaults",
    "microsoft.storage/storageaccounts": "storage-accounts",
    "microsoft.operationalinsights/workspaces": "log-analytics-workspaces",
}


def friendly_type(azure_type: str) -> str:
    """Convert azure type to filesystem-friendly directory name."""
    return RESOURCE_TYPE_MAP.get(azure_type.lower(), azure_type.lower().replace("/", "--"))


def resource_key(r: dict) -> str:
    """Return a unique key: rg/type-dir/name."""
    return f"{r['resourceGroup']}/{friendly_type(r['type'])}/{r['name']}"


def _name_from_id(resource_id: str) -> Optional[str]:
    """Extract the resource name (last segment) from an ARM resource ID."""
    if not resource_id:
        return None
    return resource_id.rstrip("/").rsplit("/", 1)[-1]


def _find_resource_by_name(name: str, resources: List[dict]) -> Optional[dict]:
    """Find a resource by name (case-insensitive)."""
    for r in resources:
        if r["name"].lower() == name.lower():
            return r
    return None


# App setting names that indicate specific Azure service dependencies
_STORAGE_SETTINGS = {
    "azurewebjobsstorage",
    "azurewebjobsdashboard",
    "website_contentazurefileconnectionstring",
}

# Settings whose value is a plain storage account name (no connection string)
_STORAGE_NAME_SETTINGS = {
    "storage_account_name",
    "storageaccountname",
    "azure_storage_account",
    "blob_storage_account",
}

_APPINSIGHTS_SETTINGS = {
    "appinsights_instrumentationkey",
    "applicationinsights_connection_string",
    "appinsights_profilerfeature_version",
}

_KEYVAULT_SETTINGS = {
    "keyvaulturi",
    "keyvault_uri",
    "key_vault_uri",
}

# Settings whose value is a managed identity client ID
_IDENTITY_SETTINGS = {
    "azure_client_id",
    "identity_client_id",
    "managed_identity_client_id",
    "uami_client_id",
}

# Regex patterns for extracting resource references from setting values
_STORAGE_ACCOUNT_PATTERN = re.compile(
    r"(?:AccountName=|https?://)([a-z0-9]{3,24})(?:\.(?:blob|table|queue|file|dfs)\.core\.windows\.net|;)",
    re.IGNORECASE,
)
_KEYVAULT_URI_PATTERN = re.compile(
    r"https://([^.]+)\.vault\.azure\.net", re.IGNORECASE,
)
_APPINSIGHTS_CONNSTR_PATTERN = re.compile(
    r"InstrumentationKey=([0-9a-f-]{36})", re.IGNORECASE,
)


def _extract_edges_from_app_settings(
    src_key: str,
    app_settings: List[dict],
    lookup: Dict[str, dict],
) -> List[Tuple[str, str, str]]:
    """
    Scan app settings for hidden dependency edges.

    Discovers connections to:
      - Storage Accounts  (AzureWebJobsStorage, connection strings)
      - Key Vaults        (KeyVaultUri, @Microsoft.KeyVault references)
      - App Insights      (APPINSIGHTS_INSTRUMENTATIONKEY, connection strings)
      - Any vault reference in @Microsoft.KeyVault(...) syntax
    """
    edges = []
    seen = set()  # Deduplicate edges

    for setting in app_settings:
        name = (setting.get("name") or "").strip()
        value = (setting.get("value") or "").strip()
        name_lower = name.lower()

        if not value:
            continue

        # --- Storage Account references ---
        if name_lower in _STORAGE_SETTINGS or _STORAGE_ACCOUNT_PATTERN.search(value):
            match = _STORAGE_ACCOUNT_PATTERN.search(value)
            if match:
                sa_name = match.group(1).lower()
                sa = lookup.get(sa_name)
                if sa:
                    edge_key = (src_key, resource_key(sa), "uses-storage")
                    if edge_key not in seen:
                        edges.append(edge_key)
                        seen.add(edge_key)

        # --- Key Vault references (direct URI) ---
        if name_lower in _KEYVAULT_SETTINGS or _KEYVAULT_URI_PATTERN.search(value):
            match = _KEYVAULT_URI_PATTERN.search(value)
            if match:
                kv_name = match.group(1).lower()
                kv = lookup.get(kv_name)
                if kv:
                    edge_key = (src_key, resource_key(kv), "reads-secrets-from")
                    if edge_key not in seen:
                        edges.append(edge_key)
                        seen.add(edge_key)

        # --- @Microsoft.KeyVault(...) references in any setting value ---
        if "@Microsoft.KeyVault(" in value:
            kv_ref_match = _KEYVAULT_URI_PATTERN.search(value)
            if kv_ref_match:
                kv_name = kv_ref_match.group(1).lower()
                kv = lookup.get(kv_name)
                if kv:
                    edge_key = (src_key, resource_key(kv), "reads-secrets-from")
                    if edge_key not in seen:
                        edges.append(edge_key)
                        seen.add(edge_key)

        # --- App Insights references ---
        if name_lower in _APPINSIGHTS_SETTINGS:
            # App Insights is often not in the same RG, so we can't always
            # resolve it. Record the edge if we find a matching workspace.
            conn_match = _APPINSIGHTS_CONNSTR_PATTERN.search(value)
            if conn_match:
                ikey = conn_match.group(1).lower()
                # Try to find App Insights by instrumentationKey in properties
                for candidate in lookup.values():
                    if (candidate.get("type", "").lower() == "microsoft.insights/components"
                            and candidate.get("properties", {}).get("InstrumentationKey", "").lower() == ikey):
                        edge_key = (src_key, resource_key(candidate), "monitored-by")
                        if edge_key not in seen:
                            edges.append(edge_key)
                            seen.add(edge_key)
                        break

        # --- Plain storage account name references ---
        if name_lower in _STORAGE_NAME_SETTINGS:
            sa = lookup.get(value.lower())
            if sa and sa.get("type", "").lower() == "microsoft.storage/storageaccounts":
                edge_key = (src_key, resource_key(sa), "uses-storage")
                if edge_key not in seen:
                    edges.append(edge_key)
                    seen.add(edge_key)

        # --- Managed Identity client ID references ---
        if name_lower in _IDENTITY_SETTINGS:
            client_id = value.lower()
            for candidate in lookup.values():
                if (candidate.get("type", "").lower() == "microsoft.managedidentity/userassignedidentities"
                        and candidate.get("properties", {}).get("clientId", "").lower() == client_id):
                    edge_key = (src_key, resource_key(candidate), "uses-identity")
                    if edge_key not in seen:
                        edges.append(edge_key)
                        seen.add(edge_key)
                    break

    return edges


def extract_edges(resources: List[dict]) -> List[Tuple[str, str, str]]:
    """
    Extract dependency edges from resource properties.

    Returns list of (source_key, target_key, relationship_label) tuples.
    source depends on target.
    """
    lookup = {r["name"].lower(): r for r in resources}
    edges = []

    for r in resources:
        rtype = r["type"].lower()
        props = r.get("properties", {})
        src = resource_key(r)

        # --- Disk → VM ---
        if rtype == "microsoft.compute/disks":
            managed_by = props.get("managedBy")
            if managed_by:
                vm_name = _name_from_id(managed_by)
                vm = lookup.get(vm_name.lower()) if vm_name else None
                if vm:
                    edges.append((src, resource_key(vm), "attached-to"))

        # --- NIC → VM ---
        elif rtype == "microsoft.network/networkinterfaces":
            vm_ref = props.get("virtualMachine")
            if vm_ref and vm_ref.get("id"):
                vm_name = _name_from_id(vm_ref["id"])
                vm = lookup.get(vm_name.lower()) if vm_name else None
                if vm:
                    edges.append((src, resource_key(vm), "attached-to"))

        # --- Public IP → NIC or LB ---
        elif rtype == "microsoft.network/publicipaddresses":
            ip_config = props.get("ipConfiguration")
            if ip_config and ip_config.get("id"):
                # The ipConfiguration ID contains the parent resource
                config_id = ip_config["id"]
                # Extract the parent resource name (NIC or LB)
                parts = config_id.split("/")
                for i, part in enumerate(parts):
                    if part.lower() in ("networkinterfaces", "loadbalancers") and i + 1 < len(parts):
                        parent_name = parts[i + 1]
                        parent = lookup.get(parent_name.lower())
                        if parent:
                            edges.append((src, resource_key(parent), "assigned-to"))
                        break

        # --- NSG → NICs ---
        elif rtype == "microsoft.network/networksecuritygroups":
            for nic_ref in props.get("networkInterfaces", []):
                nic_name = _name_from_id(nic_ref.get("id", ""))
                nic = lookup.get(nic_name.lower()) if nic_name else None
                if nic:
                    edges.append((src, resource_key(nic), "applied-to"))

        # --- Container App → Environment + Key Vault ---
        elif rtype == "microsoft.app/containerapps":
            env_id = props.get("managedEnvironmentId")
            if env_id:
                env_name = _name_from_id(env_id)
                env = lookup.get(env_name.lower()) if env_name else None
                if env:
                    edges.append((src, resource_key(env), "hosted-in"))

            # Key Vault references from secrets
            config = props.get("configuration") or {}
            for secret in config.get("secrets") or []:
                kv_url = secret.get("keyVaultUrl", "")
                kv_match = re.match(r"https://([^.]+)\.vault\.azure\.net", kv_url)
                if kv_match:
                    kv_name = kv_match.group(1)
                    kv = lookup.get(kv_name.lower())
                    if kv:
                        edges.append((src, resource_key(kv), "reads-secrets-from"))

        # --- App Service / Function App → Plan + dependencies from app settings ---
        elif rtype == "microsoft.web/sites":
            plan_id = props.get("serverFarmId")
            if plan_id:
                plan_name = _name_from_id(plan_id)
                plan = lookup.get(plan_name.lower()) if plan_name else None
                if plan:
                    edges.append((src, resource_key(plan), "hosted-on"))

            # Scan app settings for hidden dependency edges
            site_config = props.get("siteConfig") or {}
            app_settings = site_config.get("appSettings") or []
            edges.extend(_extract_edges_from_app_settings(src, app_settings, lookup))

        # --- Container App Environment → Log Analytics ---
        elif rtype == "microsoft.app/managedenvironments":
            logs_config = props.get("appLogsConfiguration") or {}
            la_config = logs_config.get("logAnalyticsConfiguration") or {}
            customer_id = la_config.get("customerId")
            if customer_id:
                # Find workspace by customerId property match
                for candidate in resources:
                    if (candidate["type"].lower() == "microsoft.operationalinsights/workspaces"
                            and candidate.get("properties", {}).get("customerId") == customer_id):
                        edges.append((src, resource_key(candidate), "logs-to"))
                        break

        # --- App Insights → Log Analytics Workspace ---
        elif rtype == "microsoft.insights/components":
            workspace_id = props.get("WorkspaceResourceId") or props.get("workspaceResourceId")
            if workspace_id:
                ws_name = _name_from_id(workspace_id)
                if ws_name:
                    target = lookup.get(ws_name.lower())
                    if target:
                        edges.append((src, resource_key(target), "logs-to"))

        # --- Smart Detector Alert Rules → scoped resources ---
        elif rtype in (
            "microsoft.alertsmanagement/smartdetectoralertrules",
            "microsoft.insights/metricalerts",
            "microsoft.insights/scheduledqueryrules",
        ):
            scope_list = props.get("scope") or props.get("scopes") or []
            for scope_id in scope_list:
                scope_name = _name_from_id(scope_id)
                if scope_name:
                    target = lookup.get(scope_name.lower())
                    if target:
                        edges.append((src, resource_key(target), "monitors"))

    return edges


def detect_candidate_orphans(resources: List[dict], edges: List[Tuple[str, str, str]]) -> List[dict]:
    """
    Detect resources that are candidate orphans.

    Returns list of dicts with: resource, reason, confidence.
    """
    # Build set of resources that are targets of edges (someone depends on them)
    # and resources that are sources of edges (they depend on something)
    edge_sources = {src for src, _, _ in edges}
    edge_targets = {tgt for _, tgt, _ in edges}

    orphans = []

    for r in resources:
        rtype = r["type"].lower()
        props = r.get("properties", {})
        key = resource_key(r)

        # --- Disks ---
        if rtype == "microsoft.compute/disks":
            if not props.get("managedBy"):
                orphans.append({
                    "resource": r,
                    "reason": f"Disk state is '{props.get('diskState', 'Unknown')}' with no managedBy VM reference",
                    "confidence": "HIGH",
                    "estimated_waste": f"{props.get('diskSizeGB', '?')}GB {props.get('sku', {}).get('name', '')} disk"
                })

        # --- NICs ---
        elif rtype == "microsoft.network/networkinterfaces":
            has_vm = props.get("virtualMachine") is not None
            has_pe = props.get("privateEndpoint") is not None
            if not has_vm and not has_pe:
                orphans.append({
                    "resource": r,
                    "reason": "NIC has no associated VM or Private Endpoint",
                    "confidence": "HIGH",
                })
            elif not has_vm and has_pe:
                # This is actually fine — it's a Private Endpoint NIC
                pass

        # --- Public IPs ---
        elif rtype == "microsoft.network/publicipaddresses":
            ip_config = props.get("ipConfiguration")
            if not ip_config or not ip_config.get("id"):
                orphans.append({
                    "resource": r,
                    "reason": "Public IP has no ipConfiguration (not attached to NIC, LB, or Gateway)",
                    "confidence": "HIGH",
                    "estimated_waste": f"Static IP {props.get('ipAddress', 'N/A')}"
                })

        # --- NSGs ---
        elif rtype == "microsoft.network/networksecuritygroups":
            has_nics = len(props.get("networkInterfaces", [])) > 0
            has_subnets = len(props.get("subnets", [])) > 0
            if not has_nics and not has_subnets:
                orphans.append({
                    "resource": r,
                    "reason": "NSG not applied to any NICs or subnets",
                    "confidence": "MEDIUM — may be intentionally kept as template",
                })

    # --- Generic: resources with no edges at all ---
    # Skip types that are inherently standalone (alerts, identities, workspaces)
    standalone_types = {
        "microsoft.alertsmanagement/smartdetectoralertrules",
        "microsoft.managedidentity/userassignedidentities",
        "microsoft.operationalinsights/workspaces",
        "microsoft.insights/components",
        "microsoft.portal/dashboards",
    }
    orphan_keys = {o["resource"]["name"] for o in orphans}  # already flagged
    for r in resources:
        key = resource_key(r)
        rtype = r["type"].lower()
        if rtype in standalone_types:
            continue
        if r["name"] in orphan_keys:
            continue
        if key not in edge_sources and key not in edge_targets:
            orphans.append({
                "resource": r,
                "reason": f"Resource has no dependency edges (not referenced by or depending on any other resource)",
                "confidence": "MEDIUM",
            })

    return orphans


def build_dependency_graph_mermaid(resources: List[dict], edges: List[Tuple[str, str, str]]) -> str:
    """Generate a Mermaid diagram of resource dependencies."""
    lines = ["graph LR"]

    # Create short node IDs
    key_to_node = {}
    counter = 0
    for r in resources:
        key = resource_key(r)
        node_id = f"n{counter}"
        key_to_node[key] = node_id
        rtype_short = friendly_type(r["type"])
        lines.append(f'    {node_id}["{r["name"]}<br/><small>{rtype_short}</small>"]')
        counter += 1

    lines.append("")

    # Add edges
    for src, tgt, label in edges:
        src_node = key_to_node.get(src)
        tgt_node = key_to_node.get(tgt)
        if src_node and tgt_node:
            lines.append(f"    {src_node} -->|{label}| {tgt_node}")

    # Style orphan nodes
    lines.append("")
    lines.append("    %% Styling")
    lines.append("    classDef orphan fill:#ff6b6b,stroke:#c0392b,color:#fff")

    return "\n".join(lines)
