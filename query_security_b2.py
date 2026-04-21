import sqlite3, json, os, time

db = os.path.join(os.environ["TEMP"], "azure-fuse", "GithubCopilotForAzure-Testing.db")
start = time.time()
conn = sqlite3.connect(db)
rows = conn.execute("SELECT name, type, raw_json, properties_json FROM resources").fetchall()

print("=== SESSION B (FUSE) -- SECURITY AUDIT ===\n")

# 1. Public Network Access
print("--- PUBLIC NETWORK ACCESS ---")
public_list = []
private_list = []

for name, rtype, raw, props_str in rows:
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    typ = rtype.split("/")[-1]
    
    pna = props.get("publicNetworkAccess")
    if pna is None:
        pna = d.get("publicNetworkAccess")
    
    # Storage uses networkAcls
    if pna is None and "networkAcls" in props:
        acls = props["networkAcls"]
        pna = "Allow" if acls.get("defaultAction") == "Allow" else "Deny"
    
    if pna is None:
        continue
    
    if str(pna).lower() in ("enabled", "true", "allow"):
        public_list.append((name, typ, pna))
    else:
        private_list.append((name, typ, pna))

print(f"\n  !! PUBLIC ACCESS ENABLED ({len(public_list)}):")
for n, t, v in public_list:
    print(f"     {n:<42} {t:<25} {v}")

print(f"\n  OK PRIVATE/RESTRICTED ({len(private_list)}):")
for n, t, v in private_list:
    print(f"     {n:<42} {t:<25} {v}")

# 2. Key Vault Security
print("\n--- KEY VAULT SECURITY ---")
for name, rtype, raw, props_str in rows:
    if "keyvault" not in rtype.lower():
        continue
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    
    purge = props.get("enablePurgeProtection", False)
    soft = props.get("enableSoftDelete", False)
    days = props.get("softDeleteRetentionInDays", "?")
    rbac = props.get("enableRbacAuthorization", False)
    pna = props.get("publicNetworkAccess", "?")
    
    icon = "OK" if purge else "!!"
    print(f"\n  {icon} {name}")
    print(f"     Purge Protection:  {'ENABLED' if purge else 'DISABLED !!'}")
    print(f"     Soft Delete:       {'Enabled' if soft else 'DISABLED'} ({days} days)")
    print(f"     RBAC Auth:         {'Enabled' if rbac else 'Disabled (access policy)'}")
    print(f"     Public Access:     {pna}")

# 3. Storage Security  
print("\n--- STORAGE ACCOUNT SECURITY ---")
for name, rtype, raw, props_str in rows:
    if "storageaccounts" not in rtype.lower():
        continue
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    
    blob_pub = props.get("allowBlobPublicAccess", None)
    https = props.get("supportsHttpsTrafficOnly", None)
    tls = props.get("minimumTlsVersion", "?")
    acls = props.get("networkAcls", {}) or {}
    default_act = acls.get("defaultAction", "?")
    shared_key = props.get("allowSharedKeyAccess", None)
    
    icon = "!!" if blob_pub else "OK"
    print(f"\n  {icon} {name}")
    print(f"     Public Blob Access:  {'ENABLED !!' if blob_pub else 'Disabled' if blob_pub is False else 'Default (disabled)'}")
    print(f"     HTTPS Only:          {'Yes' if https else 'NO !!' if https is False else '?'}")
    print(f"     Min TLS:             {tls}")
    print(f"     Network Default:     {default_act}")
    print(f"     Shared Key Access:   {'Enabled' if shared_key or shared_key is None else 'Disabled'}")

# 4. AI Services
print("\n--- COGNITIVE SERVICES / AI SECURITY ---")
for name, rtype, raw, props_str in rows:
    if "cognitiveservices" not in rtype.lower() or "projects" in rtype.lower():
        continue
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    pna = props.get("publicNetworkAccess", "?")
    local_auth = props.get("disableLocalAuth", False)
    icon = "!!" if str(pna).lower() == "enabled" else "OK"
    print(f"  {icon} {name:<42} Public: {pna}  LocalAuth: {'Disabled' if local_auth else 'ENABLED'}")

# 5. API Management
print("\n--- API MANAGEMENT SECURITY ---")
for name, rtype, raw, props_str in rows:
    if "apimanagement" not in rtype.lower():
        continue
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    pna = props.get("publicNetworkAccess", "?")
    vnet = props.get("virtualNetworkType", "None")
    icon = "!!" if str(pna).lower() == "enabled" else "OK"
    print(f"  {icon} {name:<42} Public: {pna}  VNet: {vnet}")

# Summary
elapsed = time.time() - start

kv_no_purge = 0
kv_total = 0
for name, rtype, raw, props_str in rows:
    if "keyvault" not in rtype.lower():
        continue
    kv_total += 1
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    if not props.get("enablePurgeProtection", False):
        kv_no_purge += 1

st_pub = 0
st_total = 0
for name, rtype, raw, props_str in rows:
    if "storageaccounts" not in rtype.lower():
        continue
    st_total += 1
    d = json.loads(raw) if raw else {}
    props = json.loads(props_str) if props_str else d.get("properties", {})
    if props.get("allowBlobPublicAccess", False):
        st_pub += 1

print(f"\n{'='*60}")
print(f"SECURITY SUMMARY")
print(f"{'='*60}")
print(f"  Public network access enabled:       {len(public_list)} resources")
print(f"  Key Vaults without purge protection: {kv_no_purge}/{kv_total}")
print(f"  Storage with public blob access:     {st_pub}/{st_total}")

print(f"\n=== SESSION B METRICS ===")
print(f"  Time: {elapsed:.2f}s")
print(f"  Queries: 1 SQL (all from cached FUSE collection)")
print(f"  Resources analyzed: {len(rows)}")
