"""Session B: Tag compliance audit via FUSE SQLite."""
import sqlite3, json, sys, os, time

db = os.path.join(os.environ["TEMP"], "azure-fuse", "GithubCopilotForAzure-Testing.db")
start = time.time()

conn = sqlite3.connect(db)
rows = conn.execute("SELECT name, type, raw_json FROM resources").fetchall()

required_tags = ["environment", "owner", "cost-center"]
results = []
compliant_count = 0
total = len(rows)

for name, rtype, raw in rows:
    d = json.loads(raw) if raw else {}
    tags = d.get("tags") or {}
    tag_keys = {k.lower(): v for k, v in tags.items()}
    missing = [t for t in required_tags if t not in tag_keys]
    present = [t for t in required_tags if t in tag_keys]
    is_compliant = len(missing) == 0
    if is_compliant:
        compliant_count += 1
    results.append((name, rtype.split("/")[-1], present, missing, is_compliant))

pct = (compliant_count / total * 100) if total else 0

print("=== SESSION B (FUSE) — TAG COMPLIANCE AUDIT ===")
print()
print(f"OVERALL COMPLIANCE: {compliant_count}/{total} ({pct:.0f}%)")
print(f"Required tags: {required_tags}")
print()

# Non-compliant
non_comp = [r for r in results if not r[4]]
print(f"NON-COMPLIANT RESOURCES ({len(non_comp)}):")
print(f"  {'Resource':<38} {'Type':<30} Missing Tags")
print(f"  {'-'*95}")
for name, typ, present, missing, _ in sorted(non_comp, key=lambda x: len(x[3]), reverse=True):
    print(f"  {name:<38} {typ:<30} {', '.join(missing)}")

# Compliant
comp = [r for r in results if r[4]]
if comp:
    print(f"\nFULLY COMPLIANT RESOURCES ({len(comp)}):")
    for name, typ, _, _, _ in comp:
        print(f"  {name:<38} {typ}")

# Tag coverage
print(f"\nTAG COVERAGE BREAKDOWN:")
for tag in required_tags:
    has = sum(1 for r in results if tag not in r[3])
    print(f"  {tag:<15}: {has}/{total} ({has/total*100:.0f}%)")

# By type
print(f"\nCOMPLIANCE BY RESOURCE TYPE:")
by_type = {}
for name, typ, _, missing, ok in results:
    by_type.setdefault(typ, [0, 0])
    by_type[typ][0] += 1
    if ok:
        by_type[typ][1] += 1
for typ, (tot, c) in sorted(by_type.items()):
    p = c / tot * 100
    print(f"  {typ:<35} {c}/{tot} ({p:.0f}%)")

elapsed = time.time() - start
print(f"\n=== SESSION B METRICS ===")
print(f"  Time: {elapsed:.1f}s (using cached FUSE collection)")
print(f"  Queries: 1 SQL query")
print(f"  Resources analyzed: {total}")

conn.close()
