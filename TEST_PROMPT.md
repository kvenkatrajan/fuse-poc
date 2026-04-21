# FUSE POC Test: MCP Tools vs Filesystem Projection

Controlled A/B comparison with identical questions and fixed output format.

---

## Before You Start

Replace these placeholders in BOTH prompts below:
- `{SUBSCRIPTION}` — your Azure subscription ID or name
- `{RESOURCE_GROUP}` — a resource group with VMs, disks, NICs, etc.
- `{FUSE_POC_PATH}` — path to the fuse-poc directory (e.g., C:\Users\you\source\repos\fuse-poc)

---

## SESSION A: MCP Tools Only (No FUSE)

Paste this into a fresh Copilot CLI session:

```
You are performing a controlled benchmark. Follow these instructions exactly.

TASK: Analyze the Azure resource group "{RESOURCE_GROUP}" in subscription
"{SUBSCRIPTION}" and produce a report answering these 5 questions.

RULES:
- Use Azure MCP tools to gather all information
- Do NOT use az CLI commands or shell scripts
- Track every MCP tool call you make (name and what it returned)
- Produce the report in EXACTLY the format specified below

QUESTIONS:

Q1 - RESOURCE INVENTORY
List every resource in the resource group. For each, show:
  Name | Type | Location

Q2 - CANDIDATE ORPHANED RESOURCES
Identify resources that appear to be orphaned:
  - Disks with no managedBy (not attached to any VM)
  - NICs with no virtualMachine and no privateEndpoint
  - Public IPs with no ipConfiguration
  - NSGs not applied to any NIC or subnet
For each candidate orphan, show:
  Name | Type | Reason | Confidence (HIGH/MEDIUM)

Q3 - DEPENDENCY EDGES
List every dependency relationship you can find between resources:
  Source | Target | Relationship
Examples: disk attached-to VM, NIC attached-to VM, app hosted-on plan,
container app hosted-in environment, app reads-secrets-from key vault

Q4 - IMPACT ANALYSIS
For each resource that has other resources depending on it, list:
  Resource | Would break these resources if deleted

Q5 - DEPENDENCY GRAPH
Generate a Mermaid diagram showing all resources and their relationships.

OUTPUT FORMAT (use exactly this structure):

=== REPORT: {RESOURCE_GROUP} ===

--- Q1: Resource Inventory ---
| Name | Type | Location |
| ... | ... | ... |
Total: N resources

--- Q2: Candidate Orphaned Resources ---
| Name | Type | Reason | Confidence |
| ... | ... | ... | ... |
Total: N candidate orphans

--- Q3: Dependency Edges ---
| Source | Target | Relationship |
| ... | ... | ... |
Total: N edges

--- Q4: Impact Analysis ---
| Resource | Depended on by |
| ... | ... |

--- Q5: Dependency Graph ---
```mermaid
graph LR
  ...
```

--- BENCHMARK METRICS ---
Tool calls made: N
  - [list each tool call: tool_name(params) → N results]
Total JSON tokens processed: ~N (estimate)
Reasoning steps for cross-referencing: [describe what you had to correlate manually]
```

---

## SESSION B: FUSE Filesystem Projection

Paste this into a SEPARATE fresh Copilot CLI session:

```
You are performing a controlled benchmark. Follow these instructions exactly.

SETUP: First, run this command to project Azure resources onto the filesystem:

cd {FUSE_POC_PATH}
python -m azure_fuse.cli --mcp --subscription "{SUBSCRIPTION}" --resource-groups "{RESOURCE_GROUP}" --output ./azure-snapshot --clean

TASK: Using ONLY the projected filesystem (the azure-snapshot directory),
answer these 5 questions. 

RULES:
- Use ONLY filesystem commands: Get-ChildItem, Get-Content, Select-String
- Do NOT call any Azure MCP tools or az CLI commands
- Track every filesystem command you run
- Produce the report in EXACTLY the format specified below

QUESTIONS:

Q1 - RESOURCE INVENTORY
List every resource in the resource group. For each, show:
  Name | Type | Location
Hint: Get-ChildItem the resource type directories to find resource names.
Read properties.json for type and location.

Q2 - CANDIDATE ORPHANED RESOURCES
Identify resources that appear to be orphaned.
Hint: Get-ChildItem -Recurse -Filter "_CANDIDATE_ORPHAN"
Read orphan-reason.txt in each orphan directory.

Q3 - DEPENDENCY EDGES
List every dependency relationship between resources:
  Source | Target | Relationship
Hint: Get-ChildItem -Recurse -Filter "*.ref" in depends-on directories,
then Get-Content each .ref file.

Q4 - IMPACT ANALYSIS
For each resource that has other resources depending on it, list what would break.
Hint: Get-ChildItem -Recurse -Filter "*.ref" in depended-by directories.

Q5 - DEPENDENCY GRAPH
Show the pre-generated Mermaid diagram.
Hint: Get-Content "./azure-snapshot/.../dependency-graph.md"

OUTPUT FORMAT (use exactly this structure):

=== REPORT: {RESOURCE_GROUP} ===

--- Q1: Resource Inventory ---
| Name | Type | Location |
| ... | ... | ... |
Total: N resources

--- Q2: Candidate Orphaned Resources ---
| Name | Type | Reason | Confidence |
| ... | ... | ... | ... |
Total: N candidate orphans

--- Q3: Dependency Edges ---
| Source | Target | Relationship |
| ... | ... | ... |
Total: N edges

--- Q4: Impact Analysis ---
| Resource | Depended on by |
| ... | ... |

--- Q5: Dependency Graph ---
```mermaid
graph LR
  ...
```

--- BENCHMARK METRICS ---
Tool calls made: N
  - [list each command run]
Total output tokens processed: ~N (estimate)
Reasoning steps for cross-referencing: [describe what you had to figure out yourself vs what was pre-computed]
```

---

## SESSION C: Compare Results

After running both sessions, paste the two reports into a third session:

```
I ran two sessions analyzing the same Azure resource group using different approaches.
Compare the results and produce a comparison table.

SESSION A REPORT (MCP Tools):
[paste Session A output here]

SESSION B REPORT (FUSE Filesystem):
[paste Session B output here]

Compare on these dimensions:

| Metric | Session A (MCP) | Session B (FUSE) |
|--------|-----------------|------------------|
| Tool/command calls | | |
| Tokens of data processed | | |
| Cross-referencing reasoning needed | | |
| Q1 results match? | | |
| Q2 results match? | | |
| Q3 results match? | | |
| Q4 results match? | | |
| Q5 results match? | | |
| Total wall-clock time (approx) | | |
| Works offline after initial collection? | | |

Also note:
- Any answers that differed between sessions and why
- Which approach required more LLM reasoning vs pre-computed results
- Any resources that one approach found but the other missed
```
