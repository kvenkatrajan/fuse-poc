"""
Benchmark v2: Orphaned Resource Detection — A/B/C comparison
Measures real wall-clock time and counts every `az` CLI call as a tool call.

Session A: Direct MCP-style (az CLI calls to list + inspect each resource)
Session B: FUSE Filesystem (pre-compute to filesystem, query with file reads)
Session C: FUSE SQLite (pre-compute to SQLite, query with SQL)
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
SUBSCRIPTION = "githubcopilotforazure-testing"
RESOURCE_GROUP = "rg-dev-eastus"
PROMPT = (
    "Find all orphaned resources in rg-dev-eastus — unattached disks, "
    "unused NICs, unassociated public IPs, and any other resources that "
    "appear to have no dependencies."
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FS_OUTPUT = ROOT / "azure-snapshot"
SQLITE_OUTPUT = ROOT / "bench" / "GithubCopilotForAzure-Testing.db"

# ── Instrumented az CLI runner ──────────────────────────────────────────────
az_calls = []  # list of (cmd_short, elapsed_seconds)


def run_az(cmd, label=None):
    """Run an az CLI command, track the call and timing."""
    short = label or cmd[:80]
    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, shell=True, timeout=120
        )
        elapsed = time.perf_counter() - start
        az_calls.append((short, elapsed))
        if result.returncode != 0:
            print(f"    ⚠ az error ({short}): {result.stderr[:120]}")
            return None
        return json.loads(result.stdout) if result.stdout.strip() else None
    except Exception as e:
        elapsed = time.perf_counter() - start
        az_calls.append((short, elapsed))
        print(f"    ⚠ az exception ({short}): {e}")
        return None


def estimate_tokens(text):
    return len(str(text)) // 4


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION A: Direct MCP-style (individual az CLI calls)
# ═══════════════════════════════════════════════════════════════════════════
def run_session_a():
    global az_calls
    az_calls = []
    print("\n" + "=" * 70)
    print("  SESSION A: MCP-style (Direct az CLI calls)")
    print("=" * 70)
    print(f"  Prompt: {PROMPT}\n")

    session_start = time.perf_counter()
    total_tokens = 0

    # Step 1: List all resources in the RG
    print("  [1] Listing all resources in rg-dev-eastus...")
    resources = run_az(
        f'az resource list -g {RESOURCE_GROUP} '
        f'--subscription {SUBSCRIPTION} -o json',
        label="az resource list -g rg-dev-eastus"
    )
    if not resources:
        print("  FATAL: Could not list resources")
        return None
    total_tokens += estimate_tokens(json.dumps(resources))
    print(f"      Found {len(resources)} resources ({total_tokens} est. tokens)")

    # Step 2: Inspect each resource individually (what an LLM agent would do)
    print(f"\n  [2] Inspecting each resource individually...")
    resource_details = []
    for i, r in enumerate(resources, 1):
        rid = r.get("id", "")
        name = r.get("name", "")
        rtype = r.get("type", "").split("/")[-1]
        print(f"      [{i}/{len(resources)}] {name} ({rtype})...", end="", flush=True)
        detail = run_az(
            f'az resource show --ids "{rid}" -o json',
            label=f"az resource show: {name}"
        )
        if detail:
            resource_details.append(detail)
            tokens = estimate_tokens(json.dumps(detail))
            total_tokens += tokens
            print(f" OK (~{tokens} tokens)")
        else:
            print(" SKIP")

    # Step 3: Cross-reference to find orphans (simulate LLM reasoning)
    print(f"\n  [3] Cross-referencing to find orphans...")
    cross_ref_start = time.perf_counter()

    # Step 3a: Pricing lookups (what an LLM agent would also do for cost analysis)
    service_name_map = {
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
    }
    seen_services = set()
    for r in resources:
        rtype = (r.get("type") or "").lower()
        svc = service_name_map.get(rtype)
        if svc and svc not in seen_services:
            seen_services.add(svc)
            region = r.get("location", "eastus")
            pricing = run_az(
                f'azmcp pricing get --filter "serviceName eq \'{svc}\' and armRegionName eq \'{region}\'"',
                label=f"azmcp pricing get {svc} ({region})"
            )
            if pricing:
                total_tokens += estimate_tokens(json.dumps(pricing))
    print(f"      Pricing lookups: {len(seen_services)} service types")
    cross_ref_start = time.perf_counter()

    # Build simple lookup
    name_lookup = {d.get("name", "").lower(): d for d in resource_details}
    connected = set()

    for d in resource_details:
        props = d.get("properties", {}) or {}
        rtype = (d.get("type") or "").lower()
        name = d.get("name", "")

        # Disk → VM
        if "disks" in rtype and props.get("managedBy"):
            connected.add(name.lower())
            vm = props["managedBy"].rsplit("/", 1)[-1].lower()
            connected.add(vm)

        # NIC → VM
        if "networkinterfaces" in rtype:
            vm_ref = props.get("virtualMachine", {})
            if vm_ref and vm_ref.get("id"):
                connected.add(name.lower())
                connected.add(vm_ref["id"].rsplit("/", 1)[-1].lower())

        # Public IP → NIC/LB
        if "publicipaddresses" in rtype:
            ip_cfg = props.get("ipConfiguration", {})
            if ip_cfg and ip_cfg.get("id"):
                connected.add(name.lower())

        # Container App → Environment
        if "containerapps" in rtype and not "environments" in rtype:
            env_id = props.get("managedEnvironmentId", "")
            if env_id:
                connected.add(name.lower())
                connected.add(env_id.rsplit("/", 1)[-1].lower())

        # App Insights → Log Analytics
        if "insights/components" in rtype:
            ws = props.get("WorkspaceResourceId") or props.get("workspaceResourceId")
            if ws:
                connected.add(name.lower())
                connected.add(ws.rsplit("/", 1)[-1].lower())

        # Container App Env → Log Analytics
        if "managedenvironments" in rtype:
            la = (props.get("appLogsConfiguration") or {}).get("logAnalyticsConfiguration") or {}
            if la.get("customerId"):
                connected.add(name.lower())
                # Find workspace by customerId
                for c in resource_details:
                    if "workspaces" in (c.get("type") or "").lower():
                        if (c.get("properties") or {}).get("customerId") == la["customerId"]:
                            connected.add(c["name"].lower())

        # Smart Detector Alerts → scoped resources
        if "alertsmanagement" in rtype or "metricalerts" in rtype:
            for scope_id in (props.get("scope") or props.get("scopes") or []):
                scope_name = scope_id.rsplit("/", 1)[-1].lower()
                connected.add(name.lower())
                connected.add(scope_name)

    cross_ref_time = time.perf_counter() - cross_ref_start

    # Identify orphans
    standalone_types = {
        "microsoft.alertsmanagement/smartdetectoralertrules",
        "microsoft.operationalinsights/workspaces",
        "microsoft.insights/components",
    }
    orphans_a = []
    for r in resources:
        rtype = (r.get("type") or "").lower()
        if rtype in standalone_types:
            continue
        if r["name"].lower() not in connected:
            orphans_a.append(r)

    session_time = time.perf_counter() - session_start

    # Report
    print(f"\n  --- SESSION A RESULTS ---")
    print(f"  Orphans found: {len(orphans_a)}")
    for o in orphans_a:
        print(f"    • {o['name']} ({o['type'].split('/')[-1]})")
    print(f"\n  --- SESSION A METRICS ---")
    print(f"  Total time:          {session_time:.1f}s")
    print(f"  az CLI calls:        {len(az_calls)}")
    print(f"  Tool calls (total):  {len(az_calls)} (each az = 1 tool call)")
    print(f"  Tokens ingested:     ~{total_tokens}")
    print(f"  Cross-ref reasoning: {cross_ref_time:.1f}s")

    return {
        "session": "A (MCP/az CLI)",
        "time_total": round(session_time, 1),
        "az_calls": len(az_calls),
        "tool_calls": len(az_calls),
        "tokens": total_tokens,
        "orphans_found": len(orphans_a),
        "orphan_names": sorted([o["name"] for o in orphans_a]),
        "az_call_log": list(az_calls),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION B: FUSE Filesystem
# ═══════════════════════════════════════════════════════════════════════════
def run_session_b():
    global az_calls
    az_calls = []
    print("\n" + "=" * 70)
    print("  SESSION B: FUSE Filesystem Projection")
    print("=" * 70)
    print(f"  Prompt: {PROMPT}\n")

    # ── Phase 1: Pre-computation (FUSE CLI) ──
    print("  [Phase 1] Running FUSE CLI (filesystem mode)...")
    if FS_OUTPUT.exists():
        shutil.rmtree(FS_OUTPUT)

    collection_start = time.perf_counter()

    # Monkey-patch _run_az to count calls
    import azure_fuse.mcp_collector as mcp_mod
    original_run_az = mcp_mod._run_az
    fuse_az_calls = []

    def patched_run_az(cmd):
        start = time.perf_counter()
        result = original_run_az(cmd)
        elapsed = time.perf_counter() - start
        short = cmd[:80] if len(cmd) > 80 else cmd
        fuse_az_calls.append((short, elapsed))
        return result

    mcp_mod._run_az = patched_run_az

    try:
        cmd = (
            f'python -m azure_fuse.cli --mcp '
            f'--subscription "{SUBSCRIPTION}" '
            f'--resource-groups "{RESOURCE_GROUP}" '
            f'--output "{FS_OUTPUT}" --clean'
        )
        result = subprocess.run(
            cmd, capture_output=True, text=True, shell=True,
            timeout=300, cwd=str(ROOT)
        )
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        if result.stderr:
            print(f"  stderr: {result.stderr[:300]}")
    finally:
        mcp_mod._run_az = original_run_az

    collection_time = time.perf_counter() - collection_start

    # Parse [AZ_CALL] lines from subprocess output for accurate call tracking
    az_call_log_b = []
    for line in result.stdout.split("\n"):
        if "[AZ_CALL]" in line:
            # Format: "  [AZ_CALL] <cmd> | <time>s"
            parts = line.split("[AZ_CALL]")[1].strip()
            pipe_parts = parts.rsplit("|", 1)
            call_label = pipe_parts[0].strip()
            call_time = float(pipe_parts[1].strip().rstrip("s")) if len(pipe_parts) > 1 else 0.0
            az_call_log_b.append((call_label, call_time))
    az_call_count_collection = len(az_call_log_b)

    print(f"  Collection time: {collection_time:.1f}s")
    print(f"  az CLI calls detected: {az_call_count_collection}")

    # ── Phase 2: Query (filesystem reads) ──
    print("\n  [Phase 2] Querying filesystem for orphans...")
    query_start = time.perf_counter()
    fs_tool_calls = 0
    total_tokens_b = 0

    # Find the subscription directory
    sub_dirs = list(FS_OUTPUT.iterdir())
    if not sub_dirs:
        print("  ERROR: No subscription directory found")
        return None
    sub_dir = sub_dirs[0]

    # Command 1: Find all _CANDIDATE_ORPHAN markers
    orphan_markers = list(sub_dir.rglob("_CANDIDATE_ORPHAN"))
    fs_tool_calls += 1
    total_tokens_b += estimate_tokens(str([m.parent.name for m in orphan_markers]))
    print(f"    [1] Found {len(orphan_markers)} orphan markers")

    # Command 2: Read orphan-reason.txt for each
    orphan_names_b = []
    for marker in orphan_markers:
        reason_file = marker.parent / "orphan-reason.txt"
        if reason_file.exists():
            content = reason_file.read_text()
            total_tokens_b += estimate_tokens(content)
            fs_tool_calls += 1
        orphan_names_b.append(marker.parent.name)

    # Command 3: Read orphaned-resources.txt
    orphan_summary = sub_dir / "orphaned-resources.txt"
    if orphan_summary.exists():
        content = orphan_summary.read_text()
        total_tokens_b += estimate_tokens(content)
        fs_tool_calls += 1
        print(f"    [3] Read orphan summary ({len(content)} bytes)")

    # Command 4: Read dependency graph
    dep_graph = sub_dir / "dependency-graph.md"
    if dep_graph.exists():
        content = dep_graph.read_text()
        total_tokens_b += estimate_tokens(content)
        fs_tool_calls += 1
        print(f"    [4] Read dependency graph ({len(content)} bytes)")

    # Command 5: Check .ref files for dependency edges
    ref_files = list(sub_dir.rglob("*.ref"))
    for rf in ref_files:
        content = rf.read_text()
        total_tokens_b += estimate_tokens(content)
    fs_tool_calls += 1
    print(f"    [5] Read {len(ref_files)} .ref files")

    query_time = time.perf_counter() - query_start
    total_time = collection_time + query_time

    print(f"\n  --- SESSION B RESULTS ---")
    print(f"  Orphans found: {len(orphan_markers)}")
    for name in sorted(orphan_names_b):
        print(f"    • {name}")

    print(f"\n  --- SESSION B METRICS ---")
    print(f"  Collection time:     {collection_time:.1f}s")
    print(f"  Query time:          {query_time:.2f}s")
    print(f"  Total time:          {total_time:.1f}s")
    print(f"  az CLI calls:        {az_call_count_collection} (collection only)")
    for i, (call, elapsed) in enumerate(az_call_log_b, 1):
        print(f"    [{i}] {call} ({elapsed:.1f}s)")
    print(f"  Filesystem commands: {fs_tool_calls}")
    print(f"  Tool calls (total):  {az_call_count_collection + fs_tool_calls}")
    print(f"  Tokens ingested:     ~{total_tokens_b}")

    return {
        "session": "B (FUSE Filesystem)",
        "time_total": round(total_time, 1),
        "time_collection": round(collection_time, 1),
        "time_query": round(query_time, 2),
        "az_calls": az_call_count_collection,
        "fs_commands": fs_tool_calls,
        "tool_calls": az_call_count_collection + fs_tool_calls,
        "tokens": total_tokens_b,
        "orphans_found": len(orphan_markers),
        "orphan_names": sorted(orphan_names_b),
        "az_call_log": list(az_call_log_b),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION C: FUSE SQLite
# ═══════════════════════════════════════════════════════════════════════════
def run_session_c():
    global az_calls
    az_calls = []
    print("\n" + "=" * 70)
    print("  SESSION C: FUSE SQLite Projection")
    print("=" * 70)
    print(f"  Prompt: {PROMPT}\n")

    # ── Phase 1: Pre-computation (FUSE CLI → SQLite) ──
    print("  [Phase 1] Running FUSE CLI (SQLite mode)...")
    if SQLITE_OUTPUT.exists():
        SQLITE_OUTPUT.unlink()

    collection_start = time.perf_counter()

    cmd = (
        f'python -m azure_fuse.cli --mcp '
        f'--subscription "{SUBSCRIPTION}" '
        f'--resource-groups "{RESOURCE_GROUP}" '
        f'--output "{SQLITE_OUTPUT}" '
        f'--format sqlite --clean'
    )
    result = subprocess.run(
        cmd, capture_output=True, text=True, shell=True,
        timeout=300, cwd=str(ROOT)
    )
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    if result.stderr:
        print(f"  stderr: {result.stderr[:300]}")

    collection_time = time.perf_counter() - collection_start

    # Parse [AZ_CALL] lines from subprocess output for accurate call tracking
    az_call_log_c = []
    for line in result.stdout.split("\n"):
        if "[AZ_CALL]" in line:
            parts = line.split("[AZ_CALL]")[1].strip()
            pipe_parts = parts.rsplit("|", 1)
            call_label = pipe_parts[0].strip()
            call_time = float(pipe_parts[1].strip().rstrip("s")) if len(pipe_parts) > 1 else 0.0
            az_call_log_c.append((call_label, call_time))
    az_call_count_collection = len(az_call_log_c)

    print(f"  Collection time: {collection_time:.1f}s")
    print(f"  az CLI calls detected: {az_call_count_collection}")

    if not SQLITE_OUTPUT.exists():
        print("  ERROR: SQLite DB not created")
        return None

    db_size = os.path.getsize(SQLITE_OUTPUT)

    # ── Phase 2: Query (SQL) ──
    print(f"\n  [Phase 2] Querying SQLite ({db_size / 1024:.1f} KB)...")
    query_start = time.perf_counter()
    sql_queries = 0
    total_tokens_c = 0

    db = sqlite3.connect(str(SQLITE_OUTPUT))

    # Query 1: Get all orphans with metadata
    rows1 = db.execute("""
        SELECT r.name, r.type, o.reason, o.confidence
        FROM orphans o
        JOIN resources r ON o.resource_id = r.id
        WHERE r.resource_group = 'rg-dev-eastus'
        ORDER BY o.confidence DESC, r.type, r.name
    """).fetchall()
    sql_queries += 1
    total_tokens_c += estimate_tokens(str(rows1))
    print(f"    [Q1] Orphans: {len(rows1)} rows")

    # Query 2: Cross-validate via edge table
    rows2 = db.execute("""
        SELECT r.name, r.type
        FROM resources r
        WHERE r.resource_group = 'rg-dev-eastus'
          AND r.id NOT IN (SELECT source_id FROM edges)
          AND r.id NOT IN (SELECT target_id FROM edges)
        ORDER BY r.type, r.name
    """).fetchall()
    sql_queries += 1
    total_tokens_c += estimate_tokens(str(rows2))
    print(f"    [Q2] Zero-edge validation: {len(rows2)} rows")

    # Query 3: Connected resources for context
    rows3 = db.execute("""
        SELECT r.name, r.type,
            (SELECT COUNT(*) FROM edges WHERE source_id = r.id) as out_edges,
            (SELECT COUNT(*) FROM edges WHERE target_id = r.id) as in_edges
        FROM resources r
        WHERE r.resource_group = 'rg-dev-eastus'
          AND (r.id IN (SELECT source_id FROM edges)
               OR r.id IN (SELECT target_id FROM edges))
        ORDER BY in_edges DESC
    """).fetchall()
    sql_queries += 1
    total_tokens_c += estimate_tokens(str(rows3))
    print(f"    [Q3] Connected resources: {len(rows3)} rows")

    # Query 4: Orphan cost impact via pricing JOIN
    has_pricing = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='pricing'"
    ).fetchone()[0]

    if has_pricing:
        rows4 = db.execute("""
            SELECT r.name, r.type, p.sku_name, p.monthly_estimate, p.meter_name
            FROM orphans o
            JOIN resources r ON o.resource_id = r.id
            LEFT JOIN pricing p ON r.id = p.resource_id
            WHERE r.resource_group = 'rg-dev-eastus'
            ORDER BY COALESCE(p.monthly_estimate, 0) DESC
        """).fetchall()
        sql_queries += 1
        total_tokens_c += estimate_tokens(str(rows4))
        total_waste = sum(r[3] or 0 for r in rows4)
        print(f"    [Q4] Cost impact: {len(rows4)} rows, ${total_waste:.2f}/mo waste")
    else:
        rows4 = []
        total_waste = 0
        print(f"    [Q4] Pricing table not available")

    # Query 5: Dependency graph (Mermaid)
    graph_row = db.execute(
        "SELECT content FROM artifacts WHERE name = 'dependency_graph_mermaid'"
    ).fetchone()
    sql_queries += 1
    if graph_row:
        total_tokens_c += estimate_tokens(graph_row[0])
        print(f"    [Q5] Dependency graph: {len(graph_row[0])} chars")

    query_time = time.perf_counter() - query_start
    total_time = collection_time + query_time

    orphan_names_c = sorted([r[0] for r in rows1])

    db.close()

    print(f"\n  --- SESSION C RESULTS ---")
    print(f"  Orphans found: {len(rows1)}")
    for r in rows1:
        cost_str = ""
        if has_pricing:
            matching = [x for x in rows4 if x[0] == r[0]]
            if matching and matching[0][3]:
                cost_str = f" (${matching[0][3]:.2f}/mo)"
        print(f"    • {r[0]} ({r[1].split('/')[-1]}){cost_str}")
    if total_waste > 0:
        print(f"\n  Estimated monthly waste: ${total_waste:.2f}")

    print(f"\n  --- SESSION C METRICS ---")
    print(f"  Collection time:     {collection_time:.1f}s")
    print(f"  Query time:          {query_time:.3f}s")
    print(f"  Total time:          {total_time:.1f}s")
    print(f"  az CLI calls:        {az_call_count_collection} (collection only)")
    for i, (call, elapsed) in enumerate(az_call_log_c, 1):
        print(f"    [{i}] {call} ({elapsed:.1f}s)")
    print(f"  SQL queries:         {sql_queries}")
    print(f"  Tool calls (total):  {az_call_count_collection + sql_queries}")
    print(f"  Tokens ingested:     ~{total_tokens_c}")
    print(f"  DB size:             {db_size / 1024:.1f} KB")

    return {
        "session": "C (FUSE SQLite)",
        "time_total": round(total_time, 1),
        "time_collection": round(collection_time, 1),
        "time_query": round(query_time, 3),
        "az_calls": az_call_count_collection,
        "sql_queries": sql_queries,
        "tool_calls": az_call_count_collection + sql_queries,
        "tokens": total_tokens_c,
        "orphans_found": len(rows1),
        "orphan_names": orphan_names_c,
        "db_size_kb": round(db_size / 1024, 1),
        "monthly_waste": round(total_waste, 2),
        "az_call_log": list(az_call_log_c),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  COMPARISON REPORT
# ═══════════════════════════════════════════════════════════════════════════
def generate_report(results_a, results_b, results_c):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    report = f"""## Benchmark Results 2 (v2): Orphaned Resource Detection

**Run date:** {ts}  
**Target:** `{RESOURCE_GROUP}` in subscription `{SUBSCRIPTION}`

**Prompt:**
> {PROMPT}

---

## Summary Comparison

| Metric | Session A (MCP) | Session B (Filesystem) | Session C (SQLite) |
|--------|----------------|----------------------|-------------------|
| **Total time** | {results_a['time_total']}s | {results_b['time_total']}s | {results_c['time_total']}s |
| **Query-only time** | {results_a['time_total']}s (no pre-compute) | {results_b['time_query']}s | {results_c['time_query']}s |
| **Collection time** | N/A (live) | {results_b['time_collection']}s | {results_c['time_collection']}s |
| **az CLI calls** | {results_a['az_calls']} | {results_b['az_calls']} | {results_c['az_calls']} |
| **Tool calls (total)** | {results_a['tool_calls']} | {results_b['tool_calls']} | {results_c['tool_calls']} |
| **Tokens ingested** | ~{results_a['tokens']:,} | ~{results_b['tokens']:,} | ~{results_c['tokens']:,} |
| **Orphans found** | {results_a['orphans_found']} | {results_b['orphans_found']} | {results_c['orphans_found']} |
"""

    # Token reduction
    if results_a['tokens'] > 0:
        b_reduction = round((1 - results_b['tokens'] / results_a['tokens']) * 100)
        c_reduction = round((1 - results_c['tokens'] / results_a['tokens']) * 100)
        report += f"| **Token reduction vs MCP** | baseline | ~{b_reduction}% less | ~{c_reduction}% less |\n"

    # Time reduction
    if results_a['time_total'] > 0:
        b_time_red = round((1 - results_b['time_total'] / results_a['time_total']) * 100)
        c_time_red = round((1 - results_c['time_total'] / results_a['time_total']) * 100)
        report += f"| **Time reduction vs MCP** | baseline | ~{b_time_red}% less | ~{c_time_red}% less |\n"

    if results_c.get('monthly_waste', 0) > 0:
        report += f"| **Monthly waste estimate** | N/A | N/A | ${results_c['monthly_waste']:.2f} |\n"

    report += f"""
---

## Session A: MCP-style (Direct az CLI Calls)

**Approach:** Call `az resource list` to enumerate resources, then `az resource show` for each 
resource to get full properties, then manually cross-reference to find orphans.

| Metric | Value |
|--------|-------|
| Total time | {results_a['time_total']}s |
| az CLI calls | {results_a['az_calls']} |
| Tool calls (total) | {results_a['tool_calls']} |
| Tokens ingested | ~{results_a['tokens']:,} |
| Orphans found | {results_a['orphans_found']} |

### az CLI Call Log

| # | Call | Time |
|---|------|------|
"""
    for i, (call, elapsed) in enumerate(results_a['az_call_log'], 1):
        report += f"| {i} | `{call}` | {elapsed:.1f}s |\n"

    report += f"""
---

## Session B: FUSE Filesystem

**Approach:** One-time FUSE CLI collection projects resources, edges, and orphans onto the 
local filesystem. Then query with standard file reads.

| Metric | Value |
|--------|-------|
| Collection time | {results_b['time_collection']}s |
| Query time | {results_b['time_query']}s |
| Total time | {results_b['time_total']}s |
| az CLI calls (collection) | {results_b['az_calls']} |
| Filesystem commands (query) | {results_b['fs_commands']} |
| Tool calls (total) | {results_b['tool_calls']} |
| Tokens ingested | ~{results_b['tokens']:,} |
| Orphans found | {results_b['orphans_found']} |

### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
"""
    for i, (call, elapsed) in enumerate(results_b.get('az_call_log', []), 1):
        report += f"| {i} | `{call}` | {elapsed:.1f}s |\n"

    report += f"""
---

## Session C: FUSE SQLite

**Approach:** One-time FUSE CLI collection projects everything into SQLite with orphans, edges, 
and pricing tables. Then query with SQL JOINs.

| Metric | Value |
|--------|-------|
| Collection time | {results_c['time_collection']}s |
| Query time | {results_c['time_query']}s |
| Total time | {results_c['time_total']}s |
| az CLI calls (collection) | {results_c['az_calls']} |
| SQL queries (query) | {results_c['sql_queries']} |
| Tool calls (total) | {results_c['tool_calls']} |
| Tokens ingested | ~{results_c['tokens']:,} |
| DB size | {results_c['db_size_kb']} KB |
| Orphans found | {results_c['orphans_found']} |
"""
    if results_c.get('monthly_waste', 0) > 0:
        report += f"| Monthly waste estimate | ${results_c['monthly_waste']:.2f} |\n"

    report += f"""
### az/azmcp Call Log (Collection Phase)

| # | Call | Time |
|---|------|------|
"""
    for i, (call, elapsed) in enumerate(results_c.get('az_call_log', []), 1):
        report += f"| {i} | `{call}` | {elapsed:.1f}s |\n"

    report += f"""
---

## Orphan Comparison

### Session A orphans ({results_a['orphans_found']}):
"""
    for name in results_a['orphan_names']:
        report += f"- {name}\n"

    report += f"""
### Session B orphans ({results_b['orphans_found']}):
"""
    for name in results_b['orphan_names']:
        report += f"- {name}\n"

    report += f"""
### Session C orphans ({results_c['orphans_found']}):
"""
    for name in results_c['orphan_names']:
        report += f"- {name}\n"

    # Check consistency
    all_same = (set(results_a['orphan_names']) == set(results_b['orphan_names']) == set(results_c['orphan_names']))
    if all_same:
        report += f"\n✅ **All three sessions found identical orphans.**\n"
    else:
        report += f"\n⚠️ **Orphan sets differ between sessions.**\n"
        only_a = set(results_a['orphan_names']) - set(results_c['orphan_names'])
        only_bc = set(results_c['orphan_names']) - set(results_a['orphan_names'])
        if only_a:
            report += f"  Only in A: {', '.join(sorted(only_a))}\n"
        if only_bc:
            report += f"  Only in B/C: {', '.join(sorted(only_bc))}\n"

    report += f"""
---

## Key Takeaways

1. **Token reduction:** FUSE approaches ingest ~{results_b['tokens']:,}–{results_c['tokens']:,} tokens vs ~{results_a['tokens']:,} for MCP
2. **az CLI call reduction:** Session A makes {results_a['az_calls']} az calls vs {results_b['az_calls']} for FUSE (one-time collection)
3. **Query-phase az calls:** Sessions B and C make **0** az calls during the query phase (all pre-computed)
4. **Time:** Session A takes {results_a['time_total']}s vs {results_b['time_total']}s/{results_c['time_total']}s for FUSE (including collection)
"""
    if results_c.get('monthly_waste', 0) > 0:
        report += f"5. **Cost visibility:** Only Session C surfaces the estimated **${results_c['monthly_waste']:.2f}/month** waste from orphaned resources\n"

    return report


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("  BENCHMARK v2: Orphaned Resource Detection")
    print(f"  Target: {RESOURCE_GROUP} in {SUBSCRIPTION}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Run all three sessions
    results_a = run_session_a()
    results_b = run_session_b()
    results_c = run_session_c()

    if not all([results_a, results_b, results_c]):
        print("\n⚠ Some sessions failed. Generating partial report...")

    # Generate report
    if results_a and results_b and results_c:
        report = generate_report(results_a, results_b, results_c)

        report_path = ROOT / "docs" / "benchmark-results-2-v2.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n{'=' * 70}")
        print(f"  REPORT SAVED: {report_path}")
        print(f"{'=' * 70}")

    print("\nDone.")
