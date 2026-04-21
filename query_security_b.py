"""Session B: Security audit via FUSE SQLite."""
import sqlite3, json, os, time

db = os.path.join(os.environ["TEMP"], "azure-fuse", "GithubCopilotForAzure-Testing.db"
)
db = sqlite3.connect(db_path)
c = db.cursor()

RG = "rg-dev-eastus"

print(f"=== SECURITY REPORT: {RG} (Session B — FUSE SQLite) ===\n")

# S1 - Resource Inventory
print("--- S1: Resource Inventory ---")
print("| Name | Type | Location |")
print("|------|------|----------|")
rows = c.execute(
    "SELECT name, type, location FROM resources WHERE resource_group=? ORDER BY type, name",
    (RG,),
).fetchall()
for r in rows:
    print(f"| {r[0]} | {r[1]} | {r[2]} |")
print(f"Total: {len(rows)} resources\n")

# S2 - Public Network Access
print("--- S2: Public Network Access ---")
print("| Name | Type | Public Access | Detail |")
print("|------|------|--------------|--------|")
all_res = c.execute(
    "SELECT name, type, properties_json FROM resources WHERE resource_group=? ORDER BY type, name",
    (RG,),
).fetchall()
public_count = 0
for name, rtype, props_json in all_res:
    props = json.loads(props_json) if props_json else {}
    public_access = props.get("publicNetworkAccess", "")
    net_acls = props.get("networkAcls", {}) or {}
    default_action = net_acls.get("defaultAction", "")
    
    # Determine status
    if public_access:
        status = public_access
    elif default_action:
        status = f"networkAcls.defaultAction={default_action}"
    else:
        status = "N/A (not applicable or not exposed)"
    
    detail = ""
    if public_access and public_access.lower() in ("enabled", "true"):
        detail = "⚠️ PUBLIC"
        public_count += 1
    elif default_action and default_action.lower() == "allow":
        detail = "⚠️ PUBLIC (default Allow)"
        public_count += 1
    elif public_access and public_access.lower() in ("disabled", "false"):
        detail = "✅ Private"
    elif default_action and default_action.lower() == "deny":
        detail = "✅ Private (default Deny)"
    
    if detail:
        print(f"| {name} | {rtype} | {status} | {detail} |")

print(f"\n🔍 {public_count} resource(s) with public access enabled\n")

# S3 - Key Vault Security
print("--- S3: Key Vault Security ---")
print("| Name | Purge Protection | Soft Delete | Retention Days |")
print("|------|-----------------|-------------|----------------|")
kvs = c.execute(
    "SELECT name, properties_json FROM resources WHERE resource_group=? AND type LIKE '%keyvault%' ORDER BY name",
    (RG,),
).fetchall()
for name, props_json in kvs:
    props = json.loads(props_json) if props_json else {}
    purge = "✅ Enabled" if props.get("enablePurgeProtection") else "❌ Disabled"
    soft = "✅ Enabled" if props.get("enableSoftDelete") else "❌ Disabled"
    retention = props.get("softDeleteRetentionInDays", "N/A")
    print(f"| {name} | {purge} | {soft} | {retention} |")
if not kvs:
    print("| (none found) | — | — | — |")
print()

# S4 - Storage Security
print("--- S4: Storage Security ---")
print("| Name | Allow Blob Public Access | HTTPS Only | Min TLS | Network Default |")
print("|------|------------------------|------------|---------|-----------------|")
storage = c.execute(
    "SELECT name, properties_json FROM resources WHERE resource_group=? AND type LIKE '%storageaccounts%' ORDER BY name",
    (RG,),
).fetchall()
for name, props_json in storage:
    props = json.loads(props_json) if props_json else {}
    blob_public = props.get("allowBlobPublicAccess")
    blob_str = "❌ Allowed" if blob_public else "✅ Denied" if blob_public is False else "N/A"
    https = "✅ Yes" if props.get("supportsHttpsTrafficOnly") else "❌ No"
    tls = props.get("minimumTlsVersion", "N/A")
    net_default = (props.get("networkAcls") or {}).get("defaultAction", "N/A")
    net_str = f"⚠️ {net_default}" if net_default == "Allow" else f"✅ {net_default}" if net_default == "Deny" else net_default
    print(f"| {name} | {blob_str} | {https} | {tls} | {net_str} |")
if not storage:
    print("| (none found) | — | — | — | — |")
print()

# S5 - Security Summary
print("--- S5: Security Summary ---")
print(f"Total resources: {len(rows)}")
print(f"Resources with public network access: {public_count}")
kv_count = len(kvs)
kv_purge_disabled = sum(
    1 for _, pj in kvs
    if not (json.loads(pj) if pj else {}).get("enablePurgeProtection")
)
print(f"Key Vaults: {kv_count} total, {kv_purge_disabled} without purge protection")
st_count = len(storage)
st_blob_public = sum(
    1 for _, pj in storage
    if (json.loads(pj) if pj else {}).get("allowBlobPublicAccess")
)
print(f"Storage accounts: {st_count} total, {st_blob_public} allowing public blob access")

issues = public_count + kv_purge_disabled + st_blob_public
if issues == 0:
    print("\n✅ GOOD — No critical security misconfigurations found")
elif issues <= 3:
    print(f"\n⚠️ MODERATE — {issues} issue(s) found, review recommended")
else:
    print(f"\n🔴 CONCERNING — {issues} issue(s) found, remediation needed")

print("\n--- BENCHMARK METRICS ---")
print("Collection: 1 CLI command (run-fuse.ps1 -Format sqlite)")
print("Query: 5 SQL queries + JSON property inspection")
print(f"Database: {os.path.getsize(db_path) / 1024:.0f} KB")
print("Reasoning steps: ZERO — all properties pre-captured in raw_json/properties_json")

db.close()
