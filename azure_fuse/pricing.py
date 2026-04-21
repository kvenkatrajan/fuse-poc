"""
Pricing enrichment — fetches Azure retail pricing via azmcp CLI.

Extracts unique (service_name, sku, region) tuples from collected resources,
queries azmcp pricing get for each, and returns a list of pricing rows
to be stored in the SQLite pricing table.
"""

import json
import subprocess
import sys
from typing import List, Optional


# Map Azure resource types to the service names used by the pricing API
SERVICE_NAME_MAP = {
    "microsoft.apimanagement/service": "API Management",
    "microsoft.search/searchservices": "Azure Cognitive Search",
    "microsoft.cognitiveservices/accounts": "Cognitive Services",
    "microsoft.containerregistry/registries": "Container Registry",
    "microsoft.keyvault/vaults": "Key Vault",
    "microsoft.storage/storageaccounts": "Storage",
    "microsoft.operationalinsights/workspaces": "Log Analytics",
    "microsoft.insights/components": "Application Insights",
    "microsoft.app/managedenvironments": "Azure Container Apps",
    "microsoft.app/containerapps": "Azure Container Apps",
    "microsoft.web/sites": "Azure App Service",
    "microsoft.web/serverfarms": "Azure App Service",
    "microsoft.compute/virtualmachines": "Virtual Machines",
    "microsoft.compute/disks": "Storage",
    "microsoft.dbforpostgresql/flexibleservers": "Azure Database for PostgreSQL",
    "microsoft.dbformysql/flexibleservers": "Azure Database for MySQL",
    "microsoft.sql/servers/databases": "SQL Database",
    "microsoft.cache/redis": "Redis Cache",
    "microsoft.network/publicipaddresses": "Virtual Network",
    "microsoft.network/applicationgateways": "Application Gateway",
}


def _extract_sku_info(resource: dict) -> Optional[dict]:
    """Extract SKU name, service type, and region from a resource."""
    rtype = resource.get("type", "").lower()
    location = resource.get("location", "")
    name = resource.get("name", "")

    # Get SKU from top-level or properties
    sku = resource.get("sku", {})
    if isinstance(sku, dict):
        sku_name = sku.get("name", "")
    elif isinstance(sku, str):
        sku_name = sku
    else:
        sku_name = ""

    # Also check properties.sku
    props = resource.get("properties", {}) or {}
    if not sku_name:
        p_sku = props.get("sku", {})
        if isinstance(p_sku, dict):
            sku_name = p_sku.get("name", "")

    if not sku_name:
        return None

    service_name = SERVICE_NAME_MAP.get(rtype)
    if not service_name:
        return None

    return {
        "resource_name": name,
        "resource_type": rtype,
        "sku_name": sku_name,
        "service_name": service_name,
        "region": location,
    }


def _run_azmcp_pricing(service_name: str, region: str) -> Optional[list]:
    """Call azmcp pricing get and return the prices list."""
    cmd = (
        f'azmcp pricing get '
        f'--filter "serviceName eq \'{service_name}\' and armRegionName eq \'{region}\'"'
    )
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        # Parse JSON from stdout (may have info: lines on stderr)
        stdout = result.stdout.strip()
        if not stdout:
            return None

        # Find the JSON object start
        json_start = stdout.find("{")
        if json_start < 0:
            return None

        data = json.loads(stdout[json_start:])
        return data.get("results", {}).get("prices", [])

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"    azmcp pricing error: {e}", file=sys.stderr)
        return None


def _match_sku_price(prices: list, sku_name: str, service_name: str) -> Optional[dict]:
    """Find the best matching price entry for a given SKU."""
    if not prices:
        return None

    import re
    # Normalize: insert space before version suffixes (StandardV2 → Standard V2)
    normalized = re.sub(r'([a-z])([A-Z])', r'\1 \2', sku_name)  # camelCase split
    sku_lower = normalized.lower().replace("_", " ").replace("-", " ")
    sku_lower = re.sub(r'\s+', ' ', sku_lower).strip()

    def _is_base_unit(p):
        """Filter out secondary, self-hosted, workspace pack, and CC (customer-controlled) meters."""
        meter = (p.get("meterName") or "").lower()
        return not any(x in meter for x in ["secondary", "self-hosted", "workspace", " cc "])

    def _norm_sku(s):
        """Normalize a SKU string for comparison."""
        n = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
        n = n.lower().replace("_", " ").replace("-", " ")
        return re.sub(r'\s+', ' ', n).strip()

    # Pass 1: exact skuName match, base unit only
    for p in prices:
        p_sku = _norm_sku(p.get("skuName") or "")
        if p_sku == sku_lower and _is_base_unit(p):
            return p

    # Pass 2: exact skuName match, any unit
    for p in prices:
        p_sku = _norm_sku(p.get("skuName") or "")
        if p_sku == sku_lower:
            return p

    # Pass 3: for single-word SKUs like "standard" or "basic", try appending common tier suffixes
    # e.g., ARM "standard" → pricing "Standard S1" for Search
    if " " not in sku_lower:
        for suffix in ["s1", "b1", "d1", "p1", ""]:
            candidate = f"{sku_lower} {suffix}".strip() if suffix else sku_lower
            for p in prices:
                p_sku = _norm_sku(p.get("skuName") or "")
                if p_sku == candidate and _is_base_unit(p):
                    return p

    # Pass 4: fuzzy — sku_name is a prefix of skuName, prefer shortest match
    matches = []
    for p in prices:
        p_sku = _norm_sku(p.get("skuName") or "")
        if p_sku.startswith(sku_lower) and _is_base_unit(p):
            matches.append(p)
    if matches:
        # Return the shortest skuName (most specific base match)
        matches.sort(key=lambda p: len(p.get("skuName", "")))
        return matches[0]

    return None


def enrich_with_pricing(resources: List[dict]) -> List[dict]:
    """
    For each resource with a SKU, fetch retail pricing via azmcp CLI.

    Returns a list of pricing row dicts with keys:
        resource_id, resource_name, resource_type, sku_name, service_name,
        region, retail_price, unit, meter_name, product_name, monthly_estimate
    """
    # Extract unique (service_name, region) pairs to minimize API calls
    sku_infos = []
    for r in resources:
        info = _extract_sku_info(r)
        if info:
            info["resource_id"] = r.get("id", "")
            sku_infos.append(info)

    if not sku_infos:
        print("  No SKU-bearing resources found for pricing lookup")
        return []

    # Group by (service_name, region) to batch API calls
    service_region_pairs = {}
    for info in sku_infos:
        key = (info["service_name"], info["region"])
        if key not in service_region_pairs:
            service_region_pairs[key] = []
        service_region_pairs[key].append(info)

    print(f"  Fetching pricing for {len(service_region_pairs)} service/region combinations...")

    # Fetch pricing per (service, region)
    pricing_cache = {}
    for (svc, region), infos in service_region_pairs.items():
        print(f"    {svc} in {region}...", end="")
        prices = _run_azmcp_pricing(svc, region)
        if prices:
            pricing_cache[(svc, region)] = prices
            print(f" {len(prices)} price points")
        else:
            print(" no data")

    # Match each resource to its price
    results = []
    for info in sku_infos:
        key = (info["service_name"], info["region"])
        prices = pricing_cache.get(key, [])
        match = _match_sku_price(prices, info["sku_name"], info["service_name"])

        retail_price = 0.0
        unit = ""
        meter_name = ""
        product_name = ""
        monthly_estimate = 0.0

        if match:
            retail_price = match.get("retailPrice", 0.0)
            unit = match.get("unitOfMeasure", "")
            meter_name = match.get("meterName", "")
            product_name = match.get("productName", "")
            # Estimate monthly cost (assume 730 hrs/month for hourly pricing)
            if "Hour" in unit:
                monthly_estimate = retail_price * 730
            elif "Month" in unit:
                monthly_estimate = retail_price
            elif "GB" in unit:
                monthly_estimate = retail_price  # per-GB, usage dependent
            else:
                monthly_estimate = retail_price

        results.append({
            "resource_id": info["resource_id"],
            "resource_name": info["resource_name"],
            "resource_type": info["resource_type"],
            "sku_name": info["sku_name"],
            "service_name": info["service_name"],
            "region": info["region"],
            "retail_price": retail_price,
            "unit": unit,
            "meter_name": meter_name,
            "product_name": product_name,
            "monthly_estimate": round(monthly_estimate, 2),
        })

    priced = sum(1 for r in results if r["retail_price"] > 0)
    print(f"  Matched pricing for {priced}/{len(results)} resources")

    return results
