"""
Demo data generator for the Azure FUSE POC.

Generates a realistic set of mock Azure resources including:
- VMs with attached disks and NICs
- Orphaned disks, NICs, and public IPs from deleted VMs
- Container Apps with environment and Key Vault dependencies
- App Service with App Service Plan
- A public IP attached to a Load Balancer (false-positive orphan case)
- NSGs both in-use and orphaned
"""


def generate_demo_resources():
    """Return (subscription_name, list_of_resource_dicts) with realistic mock data."""
    subscription = "contoso-production-001"

    resources = [
        # ======================================================================
        # Resource Group: app-prod-rg  (VMs, disks, NICs, PIPs, NSGs)
        # ======================================================================

        # --- Virtual Machines ---
        _vm("web-server-01", "app-prod-rg", "Standard_D4s_v3",
            disks=["web-server-01-osdisk", "web-server-01-data"],
            nics=["web-server-01-nic"]),

        _vm("api-server-01", "app-prod-rg", "Standard_D2s_v3",
            disks=["api-server-01-osdisk"],
            nics=["api-server-01-nic"]),

        # --- Disks (attached) ---
        _disk("web-server-01-osdisk", "app-prod-rg", 128, "Premium_LRS",
              managed_by="web-server-01"),
        _disk("web-server-01-data", "app-prod-rg", 256, "Premium_LRS",
              managed_by="web-server-01"),
        _disk("api-server-01-osdisk", "app-prod-rg", 128, "Premium_LRS",
              managed_by="api-server-01"),

        # --- Disks (ORPHANED - from deleted VMs) ---
        _disk("old-staging-osdisk", "app-prod-rg", 128, "Standard_LRS",
              managed_by=None),
        _disk("legacy-data-disk", "app-prod-rg", 512, "Premium_LRS",
              managed_by=None),

        # --- Network Interfaces (attached) ---
        _nic("web-server-01-nic", "app-prod-rg",
             vm="web-server-01", pip="web-server-01-pip"),
        _nic("api-server-01-nic", "app-prod-rg",
             vm="api-server-01", pip=None),

        # --- Network Interface (ORPHANED) ---
        _nic("old-staging-nic", "app-prod-rg",
             vm=None, pip="old-staging-pip"),

        # --- NIC owned by Private Endpoint (NOT orphaned — false positive case) ---
        _nic("pe-storage-nic", "app-prod-rg",
             vm=None, pip=None,
             private_endpoint="pe-contosoprodsa"),

        # --- Public IPs (attached) ---
        _pip("web-server-01-pip", "app-prod-rg", "40.76.1.100",
             attached_to_nic="web-server-01-nic"),

        # --- Public IP attached to Load Balancer (NOT orphaned — false positive) ---
        _pip("lb-frontend-pip", "app-prod-rg", "40.76.1.50",
             attached_to_lb="app-lb"),

        # --- Public IP (ORPHANED) ---
        _pip("old-staging-pip", "app-prod-rg", "40.76.1.200",
             attached_to_nic=None),

        # --- NSG (in use) ---
        _nsg("web-nsg", "app-prod-rg",
             nics=["web-server-01-nic"], subnets=["web-subnet"]),

        # --- NSG (ORPHANED) ---
        _nsg("deprecated-nsg", "app-prod-rg", nics=[], subnets=[]),

        # ======================================================================
        # Resource Group: platform-rg  (Container Apps, App Service, Key Vault)
        # ======================================================================

        # --- Container Apps ---
        {
            "name": "orders-api",
            "type": "microsoft.app/containerapps",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "managedEnvironmentId": _id("managedEnvironments", "prod-env", "platform-rg"),
                "template": {
                    "containers": [
                        {"image": "contosoacr.azurecr.io/orders-api:v2.1",
                         "name": "orders-api"}
                    ]
                },
                "configuration": {
                    "secrets": [
                        {"name": "db-connection",
                         "keyVaultUrl": "https://app-keyvault.vault.azure.net/secrets/db-conn"}
                    ]
                }
            }
        },
        {
            "name": "frontend-web",
            "type": "microsoft.app/containerapps",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "managedEnvironmentId": _id("managedEnvironments", "prod-env", "platform-rg"),
                "template": {
                    "containers": [
                        {"image": "contosoacr.azurecr.io/frontend:v3.0",
                         "name": "frontend"}
                    ]
                },
                "configuration": {
                    "ingress": {"external": True, "targetPort": 3000}
                }
            }
        },

        # --- Container App Environment ---
        {
            "name": "prod-env",
            "type": "microsoft.app/managedenvironments",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "appLogsConfiguration": {
                    "destination": "log-analytics",
                    "logAnalyticsConfiguration": {"customerId": "workspace-id-123"}
                },
                "vnetConfiguration": {
                    "infrastructureSubnetId": _id("subnets", "aca-subnet", "platform-rg")
                }
            }
        },

        # --- App Service Plan ---
        {
            "name": "premium-plan",
            "type": "microsoft.web/serverfarms",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "sku": {"name": "P1v3", "tier": "PremiumV3"},
                "numberOfWorkers": 3
            }
        },

        # --- App Service (with realistic app settings showing hidden dependencies) ---
        {
            "name": "admin-portal",
            "type": "microsoft.web/sites",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "serverFarmId": _id("serverfarms", "premium-plan", "platform-rg"),
                "state": "Running",
                "defaultHostName": "admin-portal.azurewebsites.net",
                "siteConfig": {
                    "appSettings": [
                        # Key Vault reference (direct URI)
                        {"name": "KeyVaultUri",
                         "value": "https://app-keyvault.vault.azure.net"},
                        # Key Vault reference (@Microsoft.KeyVault syntax)
                        {"name": "DatabasePassword",
                         "value": "@Microsoft.KeyVault(SecretUri=https://app-keyvault.vault.azure.net/secrets/db-password)"},
                        # Storage Account reference (connection string)
                        {"name": "AzureWebJobsStorage",
                         "value": "DefaultEndpointsProtocol=https;AccountName=contosoprodsa;AccountKey=xxx;EndpointSuffix=core.windows.net"},
                        # Storage Account reference (content share)
                        {"name": "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING",
                         "value": "DefaultEndpointsProtocol=https;AccountName=contosoprodsa;AccountKey=xxx;EndpointSuffix=core.windows.net"},
                        # App Insights (instrumentation key)
                        {"name": "APPINSIGHTS_INSTRUMENTATIONKEY",
                         "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
                        # Generic settings (no dependency)
                        {"name": "WEBSITE_NODE_DEFAULT_VERSION",
                         "value": "~18"},
                    ]
                }
            }
        },

        # --- Key Vault ---
        {
            "name": "app-keyvault",
            "type": "microsoft.keyvault/vaults",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "vaultUri": "https://app-keyvault.vault.azure.net",
                "sku": {"name": "standard"},
                "tenantId": "72f988bf-86f1-41af-91ab-2d7cd011db47"
            }
        },

        # --- Storage Account ---
        {
            "name": "contosoprodsa",
            "type": "microsoft.storage/storageaccounts",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "primaryEndpoints": {
                    "blob": "https://contosoprodsa.blob.core.windows.net/"
                },
                "sku": {"name": "Standard_GRS"}
            }
        },

        # --- Log Analytics Workspace ---
        {
            "name": "prod-workspace",
            "type": "microsoft.operationalinsights/workspaces",
            "resourceGroup": "platform-rg",
            "location": "eastus",
            "properties": {
                "sku": {"name": "PerGB2018"},
                "retentionInDays": 90,
                "customerId": "workspace-id-123"
            }
        },
    ]

    # Assign canonical IDs to resources that don't have one
    for r in resources:
        if "id" not in r:
            r["id"] = _id(_type_to_provider(r["type"]), r["name"], r["resourceGroup"])

    return subscription, resources


# ---------------------------------------------------------------------------
# Helper builders (keep demo data concise)
# ---------------------------------------------------------------------------

_SUB_ID = "00000000-0000-0000-0000-000000000001"


def _id(provider_resource, name, rg):
    return f"/subscriptions/{_SUB_ID}/resourceGroups/{rg}/providers/{provider_resource}/{name}"


def _type_to_provider(azure_type):
    """Convert 'microsoft.compute/disks' → 'Microsoft.Compute/disks'."""
    parts = azure_type.split("/")
    return f"{parts[0]}/{parts[1]}" if len(parts) == 2 else azure_type


def _vm(name, rg, size, disks=None, nics=None):
    return {
        "name": name,
        "type": "microsoft.compute/virtualmachines",
        "resourceGroup": rg,
        "location": "eastus",
        "properties": {
            "vmId": f"vm-{name}",
            "hardwareProfile": {"vmSize": size},
            "storageProfile": {
                "osDisk": {"managedDisk": {"id": _id("Microsoft.Compute/disks", disks[0], rg)}} if disks else {},
                "dataDisks": [
                    {"managedDisk": {"id": _id("Microsoft.Compute/disks", d, rg)}}
                    for d in (disks[1:] if disks else [])
                ]
            },
            "networkProfile": {
                "networkInterfaces": [
                    {"id": _id("Microsoft.Network/networkInterfaces", n, rg)}
                    for n in (nics or [])
                ]
            }
        }
    }


def _disk(name, rg, size_gb, sku, managed_by=None):
    return {
        "name": name,
        "type": "microsoft.compute/disks",
        "resourceGroup": rg,
        "location": "eastus",
        "properties": {
            "diskSizeGB": size_gb,
            "diskState": "Attached" if managed_by else "Unattached",
            "managedBy": _id("Microsoft.Compute/virtualMachines", managed_by, rg) if managed_by else None,
            "sku": {"name": sku}
        }
    }


def _nic(name, rg, vm=None, pip=None, private_endpoint=None):
    props = {
        "virtualMachine": {"id": _id("Microsoft.Compute/virtualMachines", vm, rg)} if vm else None,
        "ipConfigurations": [
            {"properties": {
                "publicIPAddress": {"id": _id("Microsoft.Network/publicIPAddresses", pip, rg)} if pip else None
            }}
        ]
    }
    if private_endpoint:
        props["privateEndpoint"] = {"id": _id("Microsoft.Network/privateEndpoints", private_endpoint, rg)}
    return {
        "name": name,
        "type": "microsoft.network/networkinterfaces",
        "resourceGroup": rg,
        "location": "eastus",
        "properties": props
    }


def _pip(name, rg, ip, attached_to_nic=None, attached_to_lb=None):
    ip_config = None
    if attached_to_nic:
        ip_config = {"id": _id("Microsoft.Network/networkInterfaces", attached_to_nic, rg) + "/ipConfigurations/ipconfig1"}
    elif attached_to_lb:
        ip_config = {"id": _id("Microsoft.Network/loadBalancers", attached_to_lb, rg) + "/frontendIPConfigurations/frontend1"}
    return {
        "name": name,
        "type": "microsoft.network/publicipaddresses",
        "resourceGroup": rg,
        "location": "eastus",
        "properties": {
            "ipAddress": ip,
            "ipConfiguration": ip_config,
            "publicIPAllocationMethod": "Static"
        }
    }


def _nsg(name, rg, nics=None, subnets=None):
    return {
        "name": name,
        "type": "microsoft.network/networksecuritygroups",
        "resourceGroup": rg,
        "location": "eastus",
        "properties": {
            "networkInterfaces": [
                {"id": _id("Microsoft.Network/networkInterfaces", n, rg)} for n in (nics or [])
            ],
            "subnets": [
                {"id": _id("Microsoft.Network/subnets", s, rg)} for s in (subnets or [])
            ]
        }
    }
