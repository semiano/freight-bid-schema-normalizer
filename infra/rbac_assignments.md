# RBAC Runbook – RXO Document Normalizer

> **Audience**: GitHub Copilot agent, DevOps engineer, or Azure administrator  
> **Goal**: Ensure every managed identity has the correct role assignments after `az deployment group create`

---

## 1. Identities Overview

| Identity | Resource | Purpose |
|---|---|---|
| **Function App MI** | `func-rxodocnorm-{env}` | Pipeline execution, blob R/W, Key Vault secrets, Foundry agent calls |
| **Streamlit Container App MI** | `rxodocnorm-streamlit-{env}-app` | Streamlit UI – blob R/W (input upload + output read), Foundry agent status queries |
| **Web App MI** *(legacy, disabled)* | `web-rxodocnorm-{env}` | Deprecated – replaced by Container App to avoid VM quota |
| **Container Worker MI** | `worker-rxodocnorm-{env}-job` | *(optional)* Heavy sandbox execution |

---

## 2. Role Matrix

### 2a. Function App (`func-rxodocnorm-{env}`)

| Scope | Role | Role Definition ID | Assigned by IaC? |
|---|---|---|---|
| Storage Account | **Storage Blob Data Owner** | `b7e6dc6d-f1e8-4753-8033-0f276bb0955b` | Yes (FC1 requires Owner) |
| Storage Account | Storage Queue Data Contributor *(if queues enabled)* | `974c5e8b-45b9-4653-ba55-5f855dd0fb88` | Yes (conditional) |
| Key Vault | **Key Vault Secrets User** | `4633458b-17de-408a-b874-0445c86b69e6` | Yes |
| Foundry Account | **Cognitive Services OpenAI User** | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | Yes (conditional) |
| Foundry Project | **Azure AI User** | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | Yes (conditional) |

### 2b. Streamlit Container App (`rxodocnorm-streamlit-{env}-app`)

| Scope | Role | Role Definition ID | Assigned by IaC? |
|---|---|---|---|
| Storage Account | **Storage Blob Data Contributor** | `ba92f5b4-2d11-453d-a403-e96b0029c9fe` | Yes |
| Foundry Account | **Cognitive Services OpenAI User** | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | Yes (conditional) |
| Foundry Project | **Azure AI User** | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | Yes (conditional) |

> **Note:** The Streamlit app uses `DefaultAzureCredential` (managed identity) for blob
> access in the cloud — no storage connection string is needed. The MI needs Contributor
> (not just Reader) because the blob-trigger flow uploads workbooks to the input container.

### 2c. Web App (`web-rxodocnorm-{env}`) — *legacy, disabled*

| Scope | Role | Role Definition ID | Assigned by IaC? |
|---|---|---|---|
| Storage Account | **Storage Blob Data Reader** | `2a2b9908-6ea1-4ae2-8e65-a410df84e7d1` | Yes |
| Foundry Account | **Cognitive Services OpenAI User** | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | Yes (conditional) |
| Foundry Project | **Azure AI User** | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | Yes (conditional) |

### 2d. Container Worker *(optional)*

Same as Function App MI above. Controlled by `assignContainerWorkerRoles` and `assignContainerWorkerFoundryRoles` params.

---

## 3. Foundry Agent Creation & Configuration

Foundry Agents are **data-plane objects** (created via SDK, not ARM/Bicep).
This section walks through the full lifecycle: prerequisite RBAC → agent creation
→ back-update Bicep params → redeploy to propagate values to all services.

### 3a. Prerequisites

Before creating agents you need:

1. **A Foundry Account + Project** — either existing or created by Bicep
   (`createFoundryProject=true`).
2. **RBAC roles assigned** — if Foundry is in the same RG, use
  `assignFoundryRoles=true` in the param file. If Foundry is in a different RG,
  assign roles manually (see Cross-RG note below).
  Required roles for Function App + Streamlit Container App identities:
  `Cognitive Services OpenAI User` + `Azure AI User` (+ `Azure AI Developer`
  for agent management/listing scenarios).
3. **`FOUNDRY_PROJECT_ENDPOINT`** — the full endpoint URL. Looks like:
   `https://<account>.services.ai.azure.com/api/projects/<project-name>`
4. **Storage account public access** — the storage account must have
   `publicNetworkAccess: Enabled` so the Container App can reach blob storage.
   The Bicep template (`storage.bicep`) sets this explicitly, but an Azure Policy
   can override it. Verify with:
   ```bash
   az storage account show --name <storage-account> --resource-group <rg> \
     --query publicNetworkAccess -o tsv   # expect "Enabled"
   ```

> **Cross-RG Foundry RBAC**: If the Foundry account lives in a **different resource
> group** from the deployment (e.g. `Demo-RG` vs `rg-rxodocnorm-dev`), Bicep's
> `existing` resource reference cannot reach it. Set `assignFoundryRoles=false` in
> the param file and assign roles manually:
>
> ```bash
> # Get identities
> FUNC_MI=$(az functionapp identity show -n func-rxodocnorm-dev -g rg-rxodocnorm-dev --query principalId -o tsv)
> STREAMLIT_MI=$(az containerapp identity show -n rxodocnorm-streamlit-dev-app -g rg-rxodocnorm-dev --query principalId -o tsv)
> FOUNDRY_ID=$(az cognitiveservices account show -n <foundry-account> -g <foundry-rg> --query id -o tsv)
>
> # Assign to each MI (repeat for both $FUNC_MI and $STREAMLIT_MI)
> for MI in $FUNC_MI $STREAMLIT_MI; do
>   az role assignment create --assignee $MI --role "Cognitive Services OpenAI User" --scope $FOUNDRY_ID
>   az role assignment create --assignee $MI --role "Azure AI User"                  --scope $FOUNDRY_ID
>   az role assignment create --assignee $MI --role "Azure AI Developer"             --scope $FOUNDRY_ID
> done
> ```

If you haven't deployed with Foundry params yet, do that first:

```bash
az deployment group create \
  --resource-group rg-rxodocnorm-dev \
  --parameters infra/main.dev.bicepparam \
  --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
              acrUsername='<acr-admin-user>' \
              acrPassword='<acr-admin-password>' \
              foundryProjectEndpoint='https://<account>.services.ai.azure.com/api/projects/proj-default' \
              assignFoundryRoles=true \
              foundryAccountName='<foundry-account-name>'
```

### 3b. Agents to Create

| # | Agent Name | Script | System Prompt Source | Model |
|---|---|---|---|---|
| 1 | `RXO-Document-Normalizer` | `scripts/deploy-foundry-agent.py` | `src/function_app/prompts/transform_planner_system.txt` | `gpt-4.1` |
| 2 | `RXO-Notes-PostProcessor` | `scripts/deploy-postprocess-agent.py` | `src/function_app/prompts/notes_postprocess_system.txt` | `gpt-4.1` |

### 3c. Step 1 — Create the Transform Planner Agent

The deploy script uses `DefaultAzureCredential` so it works with your
`az login` identity. Set the endpoint as an env var:

```bash
# Set endpoint (from your Foundry project)
export FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/proj-default"
export FOUNDRY_AGENT_NAME="RXO-Document-Normalizer"
export FOUNDRY_AGENT_VERSION="5"

# Dry-run first to verify connectivity
python scripts/deploy-foundry-agent.py --dry-run

# Create / update the agent (creates a new version)
python scripts/deploy-foundry-agent.py --bump-version
```

**On success** the script prints:
```
  Created version: 5
  Bumped FOUNDRY_AGENT_VERSION: 5 -> 5
```

> **Note:** If the agent doesn't exist yet, you must first create it in the
> Azure AI Foundry portal. The script's `create_version` call adds a new
> version to an **existing** agent. The post-processor script (`deploy-postprocess-agent.py`)
> can create the agent implicitly if it doesn't exist.

### 3d. Step 2 — Create the Notes Post-Processor Agent

```bash
export FOUNDRY_POSTPROCESS_AGENT_NAME="RXO-Notes-PostProcessor"
export FOUNDRY_POSTPROCESS_AGENT_VERSION="1"

# Dry-run
python scripts/deploy-postprocess-agent.py --dry-run

# Create / update
python scripts/deploy-postprocess-agent.py --bump-version
```

### 3e. Step 3 — Capture Agent IDs (Optional)

If your agents return an `assistant_id` (for Assistants API fallback), capture it:

```bash
# List agents and find the assistant IDs
python -c "
import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ['FOUNDRY_PROJECT_ENDPOINT'],
    credential=DefaultAzureCredential()
)
for agent in client.agents.list():
    print(f'{agent.name:40s} id={agent.id}')
"
```

If the Transform Planner has an `asst_XXXX` ID, note it for the next step.

### 3f. Step 4 — Back-Update Bicep Params & Redeploy

After agents are created, update the param file with the real values and redeploy
so the Function App and Streamlit Container App get the correct env vars:

```bash
# Option A: Override at deploy time (no file changes)
az deployment group create \
  --resource-group rg-rxodocnorm-dev \
  --parameters infra/main.dev.bicepparam \
  --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
              acrUsername='<acr-admin-user>' \
              acrPassword='<acr-admin-password>' \
              foundryProjectEndpoint='https://<account>.services.ai.azure.com/api/projects/proj-default' \
              foundryAgentName='RXO-Document-Normalizer' \
              foundryAgentVersion='5' \
              foundryAssistantId='' \
              foundryPostProcessAgentName='RXO-Notes-PostProcessor' \
              foundryPostProcessAgentVersion='1' \
              assignFoundryRoles=true \
              foundryAccountName='<foundry-account-name>' \
              plannerMode='live' \
              postprocessMode='live'

# Option B: Update the param file permanently (recommended for prod)
#   Edit infra/main.dev.bicepparam and set:
#     param foundryProjectEndpoint = 'https://<account>.services.ai.azure.com/api/projects/proj-default'
#     param foundryAgentVersion = '5'
#     param plannerMode = 'live'
#     param postprocessMode = 'live'
#     param assignFoundryRoles = true
#     param foundryAccountName = '<foundry-account-name>'
#   Then: az deployment group create --resource-group rg-rxodocnorm-dev \
#           --parameters infra/main.dev.bicepparam \
#           --parameters acrLoginServer=... acrUsername=... acrPassword=...
```

### 3g. What the Redeploy Propagates

The redeploy pushes the Foundry config into **both services simultaneously**:

| Env Var | Function App | Streamlit Container App | Effect |
|---|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | `additionalAppSettings` | Container env | Live planner + agent status page work |
| `FOUNDRY_AGENT_NAME` | `additionalAppSettings` | Container env | Agent reference invocation uses correct name |
| `FOUNDRY_AGENT_VERSION` | `additionalAppSettings` | Container env | Pins specific agent version |
| `FOUNDRY_ASSISTANT_ID` | `additionalAppSettings` | Container env | *(optional)* Assistants API fallback ID |
| `PLANNER_MODE` | `additionalAppSettings` | Container env | Switches from `mock` → `live` |
| `POSTPROCESS_MODE` | `additionalAppSettings` | Container env | Switches from `mock` → `live` |

### 3h. Verification

After redeploy, verify the agents are reachable:

```bash
# 1. Streamlit System Agents page — should show agent cards with ✅ status
curl -s "https://$(az containerapp show \
  --name rxodocnorm-streamlit-dev-app \
  --resource-group rg-rxodocnorm-dev \
  --query properties.configuration.ingress.fqdn -o tsv)/_stcore/health"

# 2. Function App — run a test blob through the pipeline
#    Upload a test workbook to the 'input' container and check
#    the 'output' container for .planner.json results

# 3. Check the planner invocation report in the pipeline output
#    Look for: "path": "agent_reference", "agent_name": "RXO-Document-Normalizer"
```

### 3i. Agent Lifecycle Summary

```
┌─────────────────────────────────────────────────────────────┐
│  1. Deploy infra (Bicep) with Foundry RBAC enabled          │
│     └─→ Creates: Account ref, Project, RBAC roles          │
│                                                             │
│  2. Create agents (Python scripts)                          │
│     └─→ Creates: Agent versions in Foundry data plane      │
│                                                             │
│  3. Back-update Bicep params + Redeploy                     │
│     └─→ Pushes: FOUNDRY_* env vars to Function App         │
│                 + Streamlit Container App                   │
│                                                             │
│  4. Switch to live mode                                     │
│     └─→ plannerMode='live', postprocessMode='live'          │
│                                                             │
│  5. Update agent prompts (ongoing)                          │
│     └─→ Run deploy script with --bump-version               │
│     └─→ Redeploy Bicep with new foundryAgentVersion         │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Step-by-Step RBAC Verification

Run these commands after each deployment. Replace `<principal-id>` with the actual identity object ID.

### 4a. Get Principal IDs

```bash
# Function App
FUNC_PRINCIPAL=$(az functionapp identity show \
  --name func-rxodocnorm-dev \
  --resource-group rg-rxodocnorm-dev \
  --query principalId -o tsv)

# Streamlit Container App
STREAMLIT_PRINCIPAL=$(az containerapp show \
  --name rxodocnorm-streamlit-dev-app \
  --resource-group rg-rxodocnorm-dev \
  --query identity.principalId -o tsv)
```

### 4b. List All Assignments for a Principal

```bash
az role assignment list --assignee-object-id "$FUNC_PRINCIPAL" --all -o table
az role assignment list --assignee-object-id "$STREAMLIT_PRINCIPAL" --all -o table
```

### 4c. Validate Specific Scope

```bash
STORAGE_ID=$(az storage account show --name stxodocnormdev --resource-group rg-rxodocnorm-dev --query id -o tsv)
az role assignment list --assignee-object-id "$FUNC_PRINCIPAL" --scope "$STORAGE_ID" -o table
```

### 4d. Expected Output Checklist

- [ ] Function App has **Storage Blob Data Owner** on storage account
- [ ] Function App has **Key Vault Secrets User** on Key Vault
- [ ] Function App has **Cognitive Services OpenAI User** on Foundry account *(if Foundry enabled)*
- [ ] Function App has **Azure AI User** on Foundry project *(if Foundry enabled)*
- [ ] Streamlit Container App has **Storage Blob Data Contributor** on storage account
- [ ] Streamlit Container App has **Cognitive Services OpenAI User** on Foundry account *(if Foundry enabled)*
- [ ] Streamlit Container App has **Azure AI User** on Foundry project *(if Foundry enabled)*

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `AuthorizationFailed` on blob read | Missing Storage Blob Data Owner/Contributor | Re-run `az deployment group create` or manually assign role |
| `AuthorizationFailure` on blob upload (not `PermissionMismatch`) | Storage account `publicNetworkAccess` is `Disabled` — Container Apps are **not** on Azure's trusted-service bypass list | Enable public access: `az storage account update --name <account> --resource-group <rg> --public-network-access Enabled`. The Bicep template now sets this explicitly in `storage.bicep`, but an Azure Policy or manual change can override it. |
| `403 Forbidden` from Foundry endpoint | Missing OpenAI User or AI User role | Same-RG: set `assignFoundryRoles = true` and redeploy. Cross-RG: assign roles manually on the Foundry account scope (see §3a). |
| `401 PermissionDenied` from Foundry endpoint (cross-RG) | Foundry account is in a **different resource group** — Bicep `existing` can't reference it | Assign roles manually (see §3a cross-RG note below) |
| Key Vault 403 | MI not in KV Secrets User | Check `enableRbacAuthorization` is true on KV; redeploy roles module |
| Streamlit can't upload workbook | Container App MI missing blob contributor | Ensure `assignStreamlitAppRoles = true` (default when `enableStreamlitContainerApp = true`) |
| Streamlit "missing FOUNDRY_PROJECT_ENDPOINT" | Param `foundryProjectEndpoint` is empty | Set the real endpoint in param file or as a `--parameters` override |
| Streamlit "missing INPUT_CONTAINER" | Env vars not injected into Container App | Redeploy — `INPUT_CONTAINER` and `OUTPUT_CONTAINER` are set from Bicep |

---

## 6. Environment Variable Architecture

### Where env vars come from

| Category | Source | Examples |
|---|---|---|
| **Bicep-computed** | Derived from resource outputs at deploy time | `STORAGE_ACCOUNT_NAME`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `KEY_VAULT_URI`, `FUNCTION_APP_HOSTNAME` |
| **Bicep params** | Set in `.bicepparam` files | `INPUT_CONTAINER`, `OUTPUT_CONTAINER`, `PLANNER_MODE`, `RUN_MODE`, `FOUNDRY_AGENT_NAME`, `FOUNDRY_AGENT_VERSION`, etc. |
| **Operator-supplied** | Must be provided by the operator (real endpoint, secret) | `FOUNDRY_PROJECT_ENDPOINT`, `acrUsername`, `acrPassword` |
| **MI-derived** | No env var needed — `DefaultAzureCredential` handles auth | Storage blob access (Function App + Streamlit Container App) |

### Streamlit Container App env vars

All env vars for the Streamlit Container App are injected via Bicep through the
`streamlitApp.bicep` module. No secrets need to be stored in the container.

| Env Var | Source | Notes |
|---|---|---|
| `STORAGE_ACCOUNT_NAME` | Bicep-computed | Used by `DefaultAzureCredential` for MI-based blob access |
| `FOUNDRY_PROJECT_ENDPOINT` | Bicep param (operator) | Only needed for live planner mode + Foundry agent status |
| `FUNCTION_APP_HOSTNAME` | Bicep-computed | Function App hostname for API calls |
| `INPUT_CONTAINER` | Bicep-computed | Default `input` |
| `OUTPUT_CONTAINER` | Bicep-computed | Default `output` |
| `PLANNER_MODE` | Bicep param | `mock` (default) or `live` |
| `RUN_MODE` | Bicep param | `execute_with_validation` (default) or `draft` |
| `FOUNDRY_AGENT_NAME` | Bicep param | `RXO-Document-Normalizer` |
| `FOUNDRY_AGENT_VERSION` | Bicep param | `5` |
| `FOUNDRY_API_VERSION` | Bicep param | `2025-05-15-preview` |
| `FOUNDRY_ASSISTANT_ID` | Bicep param | Optional pre-configured assistant ID |
| `FOUNDRY_POSTPROCESS_AGENT_NAME` | Bicep param | `RXO-Notes-PostProcessor` |
| `FOUNDRY_POSTPROCESS_AGENT_VERSION` | Bicep param | `1` |
| `POSTPROCESS_MODE` | Bicep param | `mock` (default) or `live` |

### Function App env vars (FC1 FlexConsumption)

Set in `functionApp.bicep` via `baseSettings` + `additionalAppSettings`:

| Env Var | Source | Notes |
|---|---|---|
| `AzureWebJobsStorage__accountName` | Bicep-computed | MI-based storage (no connection string for FC1) |
| `INPUT_CONTAINER` | Bicep-computed | Blob trigger path |
| `OUTPUT_CONTAINER` | Bicep-computed | Blob output path |
| `KEY_VAULT_URI` | Bicep-computed | Key Vault for secrets |
| `FOUNDRY_PROJECT_ENDPOINT` | Bicep param | Foundry API endpoint |
| All `FOUNDRY_*` vars | Bicep params | Passed via `additionalAppSettings` |

### No storage connection strings in production

Both the Function App (FC1) and Streamlit Container App use **managed identity**
for blob access. `AzureWebJobsStorage` (connection string) is only used in local
development with Azurite. In the cloud, `STORAGE_ACCOUNT_NAME` + RBAC replaces it.

---

## 7. GitHub Actions Secrets Required

| Secret Name | Description |
|---|---|
| `AZURE_CLIENT_ID` | Service principal / federated identity client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Target subscription ID |
| `ACR_USERNAME` | ACR admin username (for Streamlit Container App image) |
| `ACR_PASSWORD` | ACR admin password |

These are configured per environment in GitHub repo Settings → Environments.

---

## 8. Deployment Quick Reference

```bash
# Full stack deploy (dev) — pass ACR creds as overrides (not stored in param files)
az deployment group create \
  --resource-group rg-rxodocnorm-dev \
  --parameters infra/main.dev.bicepparam \
  --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
              acrUsername='<acr-admin-user>' \
              acrPassword='<acr-admin-password>'

# With Foundry endpoint
az deployment group create \
  --resource-group rg-rxodocnorm-dev \
  --parameters infra/main.dev.bicepparam \
  --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
              acrUsername='<acr-admin-user>' \
              acrPassword='<acr-admin-password>' \
              foundryProjectEndpoint='https://<account>.services.ai.azure.com/api/projects/proj-default' \
              assignFoundryRoles=true \
              foundryAccountName='<foundry-account>'

# Function App code deploy
func azure functionapp publish func-rxodocnorm-dev --python

# Streamlit image rebuild + deploy
az acr build --registry rxodocnormacr \
  --image streamlit-ui:<tag> \
  --file Dockerfile.streamlit . --no-logs

# Option A: update Container App directly (fast path)
az containerapp update \
  --name rxodocnorm-streamlit-dev-app \
  --resource-group rg-rxodocnorm-dev \
  --image rxodocnormacr.azurecr.io/streamlit-ui:<tag>

# Option B: redeploy Bicep with updated image tag
# --parameters streamlitContainerImage='streamlit-ui:<tag>'
```

---

*Last updated: Auto-generated by GHCP handoff package builder*
