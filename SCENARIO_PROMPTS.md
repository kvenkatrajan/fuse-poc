# FUSE POC Scenario Prompts

Test prompts for evaluating the FUSE filesystem projection approach across different Azure analysis scenarios.

**Target resource group:** `rg-dev-eastus` (35 resources — Container Apps, Key Vaults, AI services, APIM, ACR, Search, App Insights, Log Analytics)
**Subscription:** `githubcopilotforazure-testing`
**FUSE POC path:** `C:\Users\kvenkatrajan\source\repos\fuse-poc`

---

## SETUP (run once before Session B prompts)

```powershell
cd C:\Users\kvenkatrajan\source\repos\fuse-poc
python -m azure_fuse.cli --mcp --subscription "githubcopilotforazure-testing" --resource-groups "rg-dev-eastus" --output ./azure-snapshot --clean
```

---

## Scenario 1: Orphaned Resource Detection

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Find all candidate orphaned resources in resource group "rg-dev-eastus"
in subscription "githubcopilotforazure-testing".

RULES:
- Use Azure MCP tools only (no az CLI, no shell scripts)
- Track every MCP tool call you make
- Estimate token count for all JSON data received

Check for:
- Disks with no managedBy
- NICs with no virtualMachine and no privateEndpoint
- Public IPs with no ipConfiguration
- NSGs not applied to any NIC or subnet
- Storage accounts referenced by no other resource
- Container registries with no images or no referencing container apps

OUTPUT FORMAT:
=== ORPHAN DETECTION: rg-dev-eastus ===

| Name | Type | Reason | Confidence |
| ... | ... | ... | ... |
Total: N candidate orphans

--- METRICS ---
Tool calls: N
  - [list each tool call]
Tokens processed: ~N
Reasoning steps: [what cross-referencing did you do?]
```

### Session B (FUSE Filesystem)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Find all candidate orphaned resources using ONLY the projected filesystem
at C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot.

RULES:
- Use ONLY filesystem commands (Get-ChildItem, Get-Content, Select-String)
- Do NOT call any Azure MCP tools or az CLI
- Track every command you run
- Estimate token count for all data read

APPROACH:
1. Get-ChildItem -Path ".\azure-snapshot" -Recurse -Filter "_CANDIDATE_ORPHAN"
2. For each result, Get-Content orphan-reason.txt in the same directory
3. Also check .\azure-snapshot\GithubCopilotForAzure-Testing\orphaned-resources.txt

OUTPUT FORMAT:
=== ORPHAN DETECTION: rg-dev-eastus ===

| Name | Type | Reason | Confidence |
| ... | ... | ... | ... |
Total: N candidate orphans

--- METRICS ---
Commands run: N
  - [list each command]
Tokens processed: ~N
Reasoning steps: [what did you figure out vs what was pre-computed?]
```

---

## Scenario 2: Dependency / Impact Analysis

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Analyze resource group "rg-dev-eastus" in subscription
"githubcopilotforazure-testing" and answer:

1. List ALL dependency relationships between resources
   (Source | Target | Relationship)
2. For each Key Vault, what resources depend on it?
   If I deleted each Key Vault, what would break?
3. For each Container App Environment, what container apps run in it?
4. Generate a Mermaid dependency graph

RULES:
- Use Azure MCP tools only (no az CLI, no shell scripts)
- Track every MCP tool call and estimate tokens received
- You will need to inspect app settings, connection strings, and resource properties

OUTPUT FORMAT:
=== DEPENDENCY ANALYSIS: rg-dev-eastus ===

--- All Edges ---
| Source | Target | Relationship |
| ... | ... | ... |
Total: N edges

--- Key Vault Impact ---
| Key Vault | Would break |
| ... | ... |

--- Container App Environments ---
| Environment | Hosts these apps |
| ... | ... |

--- Mermaid Graph ---
```mermaid
graph LR
  ...
```

--- METRICS ---
Tool calls: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [what cross-referencing did you do to discover edges?]
```

### Session B (FUSE Filesystem)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Using ONLY the projected filesystem at
C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot,
answer these dependency questions.

RULES:
- ONLY filesystem commands (Get-ChildItem, Get-Content, Select-String)
- No Azure MCP tools, no az CLI
- Track every command and estimate tokens

APPROACH:
1. Edges: Get-ChildItem -Recurse -Filter "*.ref" in depends-on directories
2. Key Vault impact: Get-ChildItem in each key-vault's depended-by directory
3. Container App Environments: check depended-by for each environment
4. Mermaid: Get-Content dependency-graph.md

OUTPUT FORMAT:
=== DEPENDENCY ANALYSIS: rg-dev-eastus ===

--- All Edges ---
| Source | Target | Relationship |
| ... | ... | ... |
Total: N edges

--- Key Vault Impact ---
| Key Vault | Would break |
| ... | ... |

--- Container App Environments ---
| Environment | Hosts these apps |
| ... | ... |

--- Mermaid Graph ---
```mermaid
graph LR
  ...
```

--- METRICS ---
Commands run: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [what was pre-computed vs what did you figure out?]
```

---

## Scenario 3: Config / SKU Audit

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Audit the configuration of all resources in "rg-dev-eastus"
(subscription "githubcopilotforazure-testing"):

1. List every resource with its SKU/tier/pricing info
2. Find any resources using Premium or expensive tiers
3. Find resources with public network access enabled
4. Find any Key Vaults without soft-delete or purge protection
5. Summarize: what would you recommend changing to reduce cost or improve security?

RULES:
- Use Azure MCP tools only (no az CLI, no shell scripts)
- Track every tool call and estimate tokens
- You'll need to inspect individual resource properties

OUTPUT FORMAT:
=== CONFIG AUDIT: rg-dev-eastus ===

--- SKU/Tier Summary ---
| Name | Type | SKU/Tier | Monthly Cost Indicator |
| ... | ... | ... | ... |

--- Public Access ---
| Name | Type | Public Access Setting |
| ... | ... | ... |

--- Key Vault Security ---
| Vault | Soft Delete | Purge Protection |
| ... | ... | ... |

--- Recommendations ---
1. ...
2. ...

--- METRICS ---
Tool calls: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [what did you inspect to find these?]
```

### Session B (FUSE Filesystem)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Using ONLY the projected filesystem at
C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot,
audit the configuration of all resources in rg-dev-eastus.

RULES:
- ONLY filesystem commands (Get-ChildItem, Get-Content, Select-String)
- No Azure MCP tools, no az CLI
- Track every command and estimate tokens

APPROACH:
1. SKUs: Select-String -Path ".\azure-snapshot\*\*\properties.json" -Pattern "sku|tier" -Recurse
2. Public access: Select-String -Pattern "publicNetworkAccess" -Recurse
3. Key Vault security: Get-Content each key-vault's properties.json, check enableSoftDelete/enablePurgeProtection
4. Use findings to make recommendations

OUTPUT FORMAT:
=== CONFIG AUDIT: rg-dev-eastus ===

--- SKU/Tier Summary ---
| Name | Type | SKU/Tier | Monthly Cost Indicator |
| ... | ... | ... | ... |

--- Public Access ---
| Name | Type | Public Access Setting |
| ... | ... | ... |

--- Key Vault Security ---
| Vault | Soft Delete | Purge Protection |
| ... | ... | ... |

--- Recommendations ---
1. ...
2. ...

--- METRICS ---
Commands run: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [what was pre-computed vs what did you grep for?]
```

---

## Scenario 4: Drift Detection (Snapshot Diff)

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: I have two snapshots of resource group "rg-dev-eastus" taken at different times.
Compare them to find what changed.

Snapshot 1 (older): C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot-full
Snapshot 2 (newer): C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot

Using Azure MCP tools, query the CURRENT state of the resource group and compare
with Snapshot 1 (read from filesystem). Identify:
1. Resources added since the snapshot
2. Resources removed since the snapshot
3. Any property changes you can detect

RULES:
- Use Azure MCP tools to get current state
- Read the snapshot using filesystem commands for comparison
- Track all tool calls and estimate tokens

OUTPUT FORMAT:
=== DRIFT DETECTION: rg-dev-eastus ===

--- Added Resources ---
| Name | Type |
| ... | ... |

--- Removed Resources ---
| Name | Type |
| ... | ... |

--- Property Changes ---
| Resource | Property | Old Value | New Value |
| ... | ... | ... | ... |

--- METRICS ---
Tool calls: N
Tokens processed: ~N
Reasoning steps: [how did you compare?]
```

### Session B (FUSE Filesystem — two snapshots)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Compare two filesystem snapshots of the same Azure resource group
to detect drift/changes.

Snapshot 1 (older): C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot-full
Snapshot 2 (newer): C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot

RULES:
- Use ONLY filesystem commands (Get-ChildItem, Get-Content, Compare-Object)
- No Azure MCP tools, no az CLI
- Track every command and estimate tokens

APPROACH:
1. Compare directory listings to find added/removed resources
2. Compare properties.json files to find property changes
3. Compare dependency-graph.md to see relationship changes

OUTPUT FORMAT:
=== DRIFT DETECTION: rg-dev-eastus ===

--- Added Resources ---
| Name | Type |
| ... | ... |

--- Removed Resources ---
| Name | Type |
| ... | ... |

--- Property Changes ---
| Resource | Property | Old Value | New Value |
| ... | ... | ... | ... |

--- Dependency Changes ---
[any edges added or removed]

--- METRICS ---
Commands run: N
Tokens processed: ~N
Reasoning steps: [what did you have to figure out vs what fell out of diff?]
```

---

## Scenario 5: Security Posture Check

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Perform a security posture check on resource group "rg-dev-eastus"
in subscription "githubcopilotforazure-testing":

1. Which resources have public network access enabled?
2. Which Key Vaults lack purge protection?
3. Which storage accounts allow public blob access?
4. Which Cognitive Services accounts have public endpoints?
5. Which Container App Environments lack VNet integration?
6. Are there any API Management services on Consumption tier (no VNet)?

RULES:
- Use Azure MCP tools only
- Track every tool call and estimate tokens
- Inspect each resource's properties to answer

OUTPUT FORMAT:
=== SECURITY CHECK: rg-dev-eastus ===

| Finding | Resource | Current Setting | Recommendation |
| ... | ... | ... | ... |

Risk Summary: N high / N medium / N low findings

--- METRICS ---
Tool calls: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [how did you check each resource?]
```

### Session B (FUSE Filesystem)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Using ONLY the projected filesystem at
C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot,
perform a security posture check on rg-dev-eastus.

RULES:
- ONLY filesystem commands (Get-ChildItem, Get-Content, Select-String)
- No Azure MCP tools, no az CLI
- Track every command and estimate tokens

APPROACH:
1. Select-String -Path ".\azure-snapshot" -Recurse -Pattern "publicNetworkAccess" 
2. Select-String -Pattern "enablePurgeProtection|enableSoftDelete" -Recurse
3. Select-String -Pattern "allowBlobPublicAccess" -Recurse
4. Check each resource type's properties.json for security-relevant fields

OUTPUT FORMAT:
=== SECURITY CHECK: rg-dev-eastus ===

| Finding | Resource | Current Setting | Recommendation |
| ... | ... | ... | ... |

Risk Summary: N high / N medium / N low findings

--- METRICS ---
Commands run: N
  - [list each]
Tokens processed: ~N
Reasoning steps: [what did you grep for vs what was pre-computed?]
```

---

## Scenario 6: Resource Tagging Compliance

### Session A (MCP Tools)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Check tagging compliance for all resources in "rg-dev-eastus"
(subscription "githubcopilotforazure-testing"):

1. List all resources and their tags
2. Find resources missing required tags: "environment", "owner", "cost-center"
3. Find resources with inconsistent tag values (e.g., "prod" vs "production")
4. Produce a compliance percentage

RULES:
- Use Azure MCP tools only
- Track every tool call and estimate tokens

OUTPUT FORMAT:
=== TAGGING COMPLIANCE: rg-dev-eastus ===

--- Tag Coverage ---
| Resource | environment | owner | cost-center | Other Tags |
| ... | ... | ... | ... | ... |

--- Missing Tags ---
| Resource | Missing |
| ... | ... |

--- Inconsistencies ---
| Tag | Values Found | Recommendation |
| ... | ... | ... |

Compliance: N/M resources fully tagged (X%)

--- METRICS ---
Tool calls: N
Tokens processed: ~N
Reasoning steps: [describe]
```

### Session B (FUSE Filesystem)

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Using ONLY the projected filesystem at
C:\Users\kvenkatrajan\source\repos\fuse-poc\azure-snapshot,
check tagging compliance for rg-dev-eastus.

RULES:
- ONLY filesystem commands (Get-ChildItem, Get-Content, Select-String)
- No Azure MCP tools, no az CLI
- Track every command and estimate tokens

APPROACH:
1. Get-ChildItem -Recurse -Filter "properties.json" | ForEach { Get-Content $_ | ConvertFrom-Json | Select tags }
2. Or: Select-String -Pattern '"tags"' -Recurse across all properties.json
3. Check for environment, owner, cost-center tags

OUTPUT FORMAT:
=== TAGGING COMPLIANCE: rg-dev-eastus ===

--- Tag Coverage ---
| Resource | environment | owner | cost-center | Other Tags |
| ... | ... | ... | ... | ... |

--- Missing Tags ---
| Resource | Missing |
| ... | ... |

--- Inconsistencies ---
| Tag | Values Found | Recommendation |
| ... | ... | ... |

Compliance: N/M resources fully tagged (X%)

--- METRICS ---
Commands run: N
Tokens processed: ~N
Reasoning steps: [what did you parse vs what was pre-computed?]
```

---

## Running the Comparison

After running any Session A + B pair, paste both outputs into a new session:

```
I ran two sessions analyzing Azure resources using different approaches.
Compare the results:

SESSION A REPORT (MCP Tools):
[paste Session A output]

SESSION B REPORT (FUSE Filesystem):
[paste Session B output]

Compare on these dimensions:

| Metric | Session A (MCP) | Session B (FUSE) |
|--------|-----------------|------------------|
| Tool/command calls | | |
| Tokens processed | | |
| Cross-referencing reasoning needed | | |
| Results match? | | |
| Wall-clock time (approx) | | |
| Works offline? | | |

Note any differences in findings and which approach was more thorough.
```
