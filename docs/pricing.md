# Pricing Enrichment

FUSE enriches collected resources with exact retail pricing from the Azure Pricing API via the `azmcp` CLI tool.

## How It Works

1. **Extract SKUs** — For each collected resource, extract the SKU name from `sku.name` or `properties.sku`
2. **Group by service** — Batch resources by Azure service name + region to minimize API calls
3. **Query pricing** — Call `azmcp pricing get` with OData filter for each service/region combination
4. **Match SKUs** — Fuzzy-match the ARM SKU name to the pricing API's `skuName` field
5. **Store results** — Write matched prices to the `pricing` SQLite table

## azmcp CLI

The pricing data comes from the `azmcp` CLI (Azure MCP CLI), installed via npm:

```bash
npm install -g @azure/mcp@3.0.0-beta.3
```

This provides the `azmcp pricing get` command which queries the Azure Retail Prices API.

### Example Call

```bash
azmcp pricing get --filter "serviceName eq 'API Management' and armRegionName eq 'eastus'"
```

Returns JSON with price points:
```json
{
  "status": 200,
  "results": {
    "prices": [
      {
        "skuName": "Standard v2",
        "meterName": "Standard v2 Unit",
        "retailPrice": 0.9589,
        "unitOfMeasure": "1 Hour",
        "productName": "API Management"
      }
    ]
  }
}
```

## Service Name Mapping

ARM resource types map to pricing API service names:

| ARM Type | Pricing Service Name |
|----------|---------------------|
| `microsoft.apimanagement/service` | API Management |
| `microsoft.search/searchservices` | Azure Cognitive Search |
| `microsoft.cognitiveservices/accounts` | Cognitive Services |
| `microsoft.containerregistry/registries` | Container Registry |
| `microsoft.keyvault/vaults` | Key Vault |
| `microsoft.storage/storageaccounts` | Storage |
| `microsoft.operationalinsights/workspaces` | Log Analytics |
| `microsoft.insights/components` | Application Insights |
| `microsoft.app/containerapps` | Azure Container Apps |
| `microsoft.compute/virtualmachines` | Virtual Machines |

## SKU Matching

The ARM SKU name often differs from the pricing API's `skuName`. The matching algorithm handles this with 4 passes:

1. **Exact match** — Normalize both (camelCase split, lowercase, replace `_`/`-` with spaces) and compare. Filter to base unit meters only (exclude "secondary", "self-hosted", "workspace", "CC" variants).

2. **Exact match (any meter)** — Same normalization, but accept any meter type.

3. **Tier suffix expansion** — For single-word SKUs like `standard`, try `standard s1`, `standard b1`, etc. This handles Search where ARM says `standard` but the API says `Standard S1`.

4. **Prefix matching** — If the normalized ARM SKU is a prefix of the API skuName, take the shortest match. Prefer base unit meters.

### Examples

| ARM SKU | Pricing API skuName | Match Pass |
|---------|-------------------|------------|
| `StandardV2` | `Standard v2` | Pass 1 (camelCase split) |
| `standard` | `Standard S1` | Pass 3 (tier suffix) |
| `basic` | `Basic` | Pass 1 (exact) |
| `Developer` | `Developer` | Pass 1 (exact) |
| `Standard_LRS` | `Standard LRS` | Pass 1 (underscore → space) |

## Monthly Estimate Calculation

| Unit of Measure | Formula |
|----------------|---------|
| `1 Hour` | `price × 730` (hours/month) |
| `1 Day` | `price × 30` |
| `1 Month` | `price × 1` |
| Per-GB, per-10K, etc. | Stored as-is (usage-dependent) |

## Resources That Show $0

These are correct — not matching errors:

| SKU | Why $0 |
|-----|--------|
| Cognitive Services S0 | Pay-per-API-call, no fixed monthly fee |
| Log Analytics PerGB2018 | Pay-per-GB-ingested, no fixed monthly fee |
| ACR Basic | Per-GB storage, no fixed monthly fee (base rate: $5/month for included storage, not in per-unit API) |
| Key Vault Standard | Per-10K operations, no fixed monthly fee |
| Storage Standard_LRS | Per-GB stored, no fixed monthly fee |

## Performance

- 7 API calls for a 35-resource group (batched by service type)
- ~2 seconds per call (each authenticates independently)
- Total: ~14 seconds added to collection time
- Without pricing: ~9 seconds; with pricing: ~23 seconds
