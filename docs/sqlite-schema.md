# SQLite Schema Reference

The FUSE SQLite database contains 5 tables that together provide a complete view of an Azure resource group's resources, relationships, costs, and health.

## Tables

### `resources`

Core table — one row per Azure resource with full ARM properties stored as JSON.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | Full ARM resource ID (`/subscriptions/.../providers/...`) |
| `resource_key` | TEXT UNIQUE | Short key: `type/name` (e.g., `key-vaults/kv-dev-eastus`) |
| `name` | TEXT | Resource name |
| `type` | TEXT | ARM type (e.g., `microsoft.keyvault/vaults`) |
| `resource_group` | TEXT | Resource group name |
| `location` | TEXT | Azure region |
| `raw_json` | TEXT | Full resource JSON from ARM (includes `tags`, `sku`, `kind`, `identity`) |
| `properties_json` | TEXT | Just the `properties` object (security settings, configs, etc.) |

**Common queries:**
```sql
-- All resources
SELECT name, type, location FROM resources;

-- Extract tags
SELECT name, json_extract(raw_json, '$.tags') FROM resources;

-- Extract SKU
SELECT name, json_extract(raw_json, '$.sku.name') as sku FROM resources;

-- Security: check publicNetworkAccess
SELECT name, type, json_extract(properties_json, '$.publicNetworkAccess') as pna
FROM resources
WHERE json_extract(properties_json, '$.publicNetworkAccess') IS NOT NULL;

-- Key Vault purge protection
SELECT name, json_extract(properties_json, '$.enablePurgeProtection') as purge
FROM resources WHERE type LIKE '%keyvault%';
```

---

### `edges`

Dependency relationships between resources. Each row represents a directional edge: `source → depends on → target`.

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | TEXT FK | ARM ID of the dependent resource |
| `target_id` | TEXT FK | ARM ID of the dependency |
| `source_key` | TEXT | Short key of source (e.g., `container-apps/my-app`) |
| `target_key` | TEXT | Short key of target (e.g., `key-vaults/my-kv`) |
| `relationship` | TEXT | Type of dependency (e.g., `key_vault_reference`, `subnet_association`) |

**Indexes:** `idx_edges_source`, `idx_edges_target` for fast lookups.

**Common queries:**
```sql
-- All dependency edges
SELECT source_key, relationship, target_key FROM edges;

-- What depends on a specific resource? (impact analysis)
SELECT source_key, relationship FROM edges
WHERE target_key LIKE '%my-keyvault%';

-- What does a resource depend on?
SELECT target_key, relationship FROM edges
WHERE source_key LIKE '%my-app%';

-- Resources with most dependents (highest blast radius)
SELECT target_key, COUNT(*) as dependent_count
FROM edges GROUP BY target_key ORDER BY dependent_count DESC;
```

**Relationship types detected:**
- `key_vault_reference` — App settings reference Key Vault secrets
- `subnet_association` — Resource deployed into a VNet subnet
- `app_insights_connection` — Connected to Application Insights
- `log_analytics_workspace` — Logs sent to Log Analytics
- `managed_environment` — Container App → Container App Environment
- `storage_account_reference` — Function App → Storage Account
- `disk_attachment` — Managed Disk → VM
- `nic_attachment` — Network Interface → VM
- `nsg_association` — NSG → NIC or Subnet

---

### `orphans`

Resources identified as potential orphans (no dependencies, likely unused).

| Column | Type | Description |
|--------|------|-------------|
| `resource_id` | TEXT FK | ARM resource ID |
| `reason` | TEXT | Why it's considered orphaned |
| `confidence` | TEXT | `high`, `medium`, or `low` |
| `estimated_waste` | TEXT | Estimated monthly cost if applicable |

**Common queries:**
```sql
-- All orphans with details
SELECT r.name, r.type, o.reason, o.confidence
FROM orphans o JOIN resources r ON o.resource_id = r.id;

-- Orphans with cost impact
SELECT r.name, r.type, o.reason, p.monthly_estimate
FROM orphans o
JOIN resources r ON o.resource_id = r.id
LEFT JOIN pricing p ON r.id = p.resource_id
WHERE COALESCE(p.monthly_estimate, 0) > 0
ORDER BY p.monthly_estimate DESC;

-- Count orphans by type
SELECT r.type, COUNT(*) FROM orphans o
JOIN resources r ON o.resource_id = r.id
GROUP BY r.type ORDER BY COUNT(*) DESC;
```

---

### `pricing`

Retail pricing from the Azure Pricing API via `azmcp pricing get`. One row per priced resource.

| Column | Type | Description |
|--------|------|-------------|
| `resource_id` | TEXT FK | ARM resource ID |
| `resource_name` | TEXT | Resource name |
| `resource_type` | TEXT | ARM type |
| `sku_name` | TEXT | SKU from ARM (e.g., `StandardV2`, `basic`, `S0`) |
| `service_name` | TEXT | Pricing API service name (e.g., `API Management`) |
| `region` | TEXT | Azure region |
| `retail_price` | REAL | Price per unit |
| `unit` | TEXT | Unit of measure (e.g., `1 Hour`, `1 GB/Month`) |
| `meter_name` | TEXT | Pricing meter matched (e.g., `Standard v2 Unit`) |
| `product_name` | TEXT | Product name from API |
| `monthly_estimate` | REAL | Estimated monthly cost (hourly × 730, etc.) |

**Common queries:**
```sql
-- Most expensive resources
SELECT resource_name, sku_name, monthly_estimate
FROM pricing WHERE monthly_estimate > 0
ORDER BY monthly_estimate DESC;

-- Total monthly spend (fixed costs)
SELECT SUM(monthly_estimate) as total FROM pricing;

-- Cost by resource type
SELECT resource_type, SUM(monthly_estimate) as total
FROM pricing GROUP BY resource_type ORDER BY total DESC;

-- Consolidation candidates (duplicate type + SKU)
SELECT resource_type, sku_name, COUNT(*) as cnt, SUM(monthly_estimate) as total
FROM pricing GROUP BY resource_type, sku_name
HAVING cnt > 1 ORDER BY total DESC;
```

**Notes on pricing:**
- Usage-based resources (Cognitive Services S0, Log Analytics PerGB2018) show `$0` — they have no fixed monthly fee
- Storage and ACR show per-GB rates — monthly estimate depends on actual usage
- Hourly resources use `× 730 hours/month` for estimates

---

### `artifacts`

Stores generated artifacts (currently the Mermaid dependency diagram).

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT PK | Artifact identifier |
| `content` | TEXT | Full artifact content |

**Common queries:**
```sql
-- Get the Mermaid dependency diagram
SELECT content FROM artifacts WHERE name = 'dependency_graph_mermaid';
```

---

## Entity Relationship Diagram

```
resources ──────┐
  │ id (PK)     │
  │              ├──< edges.source_id
  │              ├──< edges.target_id
  │              ├──< orphans.resource_id
  │              └──< pricing.resource_id
  │
artifacts (standalone — stores Mermaid graph)
```

## Data Source

All data comes from a single Azure Resource Graph query:

```kusto
resources
| project id, name, type, resourceGroup, location, tags, properties, identity, sku, kind
```

This is augmented by:
- **Relationship analysis** — scans properties for Key Vault refs, subnet IDs, connection strings
- **Orphan detection** — checks if resources have any edges; flags those without
- **Pricing enrichment** — calls `azmcp pricing get` for each unique (service, SKU, region) tuple
