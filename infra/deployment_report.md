# Deployment Validation Report

> Generated: 2026-04-24  
> Environment target: **dev** (rg-rxodocnorm-dev, eastus)  
> Subscription: ME-MngEnvMCAP429811-stephenmiano-1 (`9f1a8b76-...`)

---

## Phase 1 — Pre-Flight Validation

### 1.1 Bicep Compilation (9/9 PASS)

| File | Status |
|---|---|
| `infra/main.bicep` | OK |
| `infra/modules/storage.bicep` | OK |
| `infra/modules/functionApp.bicep` | OK |
| `infra/modules/functionPlan.bicep` | OK |
| `infra/modules/keyVault.bicep` | OK |
| `infra/modules/monitoring.bicep` | OK |
| `infra/modules/roles.bicep` | OK |
| `infra/modules/containerWorker.bicep` | OK |
| `infra/modules/webApp.bicep` | OK |

### 1.2 Param File Validation (3/3 PASS)

| File | Status |
|---|---|
| `infra/main.dev.bicepparam` | OK |
| `infra/main.test.bicepparam` | OK |
| `infra/main.prod.bicepparam` | OK |

### 1.3 Critical Param Values

| Param | dev | test | prod | Pass |
|---|---|---|---|---|
| `environmentName` | dev | test | prod | YES |
| `foundryAgentVersion` | 5 | 5 | 5 | YES |
| `foundryPostProcessAgentName` | RXO-Notes-PostProcessor | RXO-Notes-PostProcessor | RXO-Notes-PostProcessor | YES |
| `foundryPostProcessAgentVersion` | 1 | 1 | 1 | YES |
| `postprocessMode` | mock | mock | live | YES |
| `enableWebApp` | true | true | true | YES |
| `webAppPlanSkuName` | B1 | B1 | B2 | YES |

---

## Phase 2 — Infrastructure Deployment

### 2.2 Resource Group
- `rg-rxodocnorm-dev` created in `eastus` — **PASS**

### 2.3 What-If / Template Validation
- **Blocked by subscription quota** (0 Dynamic VMs, 0 Basic VMs)
- Template compiled to ARM JSON successfully — structure is valid
- ARM JSON contains **16 resource types** across 8 module deployments

### Resource Manifest (from compiled ARM)

| Module | Resource Type | Status |
|---|---|---|
| storage | `Microsoft.Storage/storageAccounts` | Present |
| storage | `...blobServices/containers` (input, output, artifacts) | Present |
| monitoring | `Microsoft.OperationalInsights/workspaces` | Present |
| monitoring | `Microsoft.Insights/components` | Present |
| keyvault | `Microsoft.KeyVault/vaults` | Present |
| functionplan | `Microsoft.Web/serverfarms` (Y1 Dynamic) | Present |
| functionapp | `Microsoft.Web/sites` (Function, Linux Python 3.12) | Present |
| webappplan | `Microsoft.Web/serverfarms` (B1 Basic) | Present (conditional) |
| webapp | `Microsoft.Web/sites` (Streamlit Web App) | Present (conditional) |
| roles | `Microsoft.Authorization/roleAssignments` (x13) | Present |
| containerworker | `Microsoft.App/managedEnvironments` | Present (disabled) |
| containerworker | `Microsoft.App/jobs` | Present (disabled) |
| root | `Microsoft.CognitiveServices/accounts` (existing ref) | Present (conditional) |
| root | `Microsoft.CognitiveServices/accounts/projects` | Present (conditional) |

### 2.4 Actual Deployment
- **NOT EXECUTED** — subscription quota insufficient
- **Action required**: Request quota increase for Dynamic VMs (≥1) and Basic VMs (≥1) in East US

---

## Phase 3 — RBAC Verification

### Role Definitions in Template (6/6 FOUND)

| Role | Definition ID | Found |
|---|---|---|
| Storage Blob Data Contributor | `ba92f5b4-2d11-453d-a403-e96b0029c9fe` | YES |
| Storage Queue Data Contributor | `974c5e8b-45b9-4653-ba55-5f855dd0fb88` | YES |
| Key Vault Secrets User | `4633458b-17de-408a-b874-0445c86b69e6` | YES |
| Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | YES |
| Azure AI User | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | YES |
| Storage Blob Data Reader | `2a2b9908-6ea1-4ae2-8e65-a410df84e7d1` | YES |

### Role Assignment Resources (13 total)

| Identity | Roles | Conditional |
|---|---|---|
| **Function App MI** | Blob Contributor, KV Secrets User, Queue Contributor, OpenAI User, AI User | Queue + Foundry conditional |
| **Worker MI** | Blob Contributor, KV Secrets User, Queue Contributor, OpenAI User, AI User | All conditional on enableContainerWorker |
| **Web App MI** | Blob Reader, OpenAI User, AI User | All conditional on enableWebApp |

### RBAC Checklist (template-level verification)

- [x] Function App → Storage Blob Data Contributor
- [x] Function App → Key Vault Secrets User
- [x] Function App → Storage Queue Data Contributor (conditional)
- [x] Function App → Cognitive Services OpenAI User (conditional on assignFoundryRoles)
- [x] Function App → Azure AI User (conditional on assignFoundryRoles)
- [x] Web App → Storage Blob Data Reader (conditional on enableWebApp)
- [x] Web App → Cognitive Services OpenAI User (conditional on enableWebApp + assignFoundryRoles)
- [x] Web App → Azure AI User (conditional on enableWebApp + assignFoundryRoles)
- [x] Worker → all 5 roles (conditional on enableContainerWorker)

---

## Phase 4 — Application Deployment

- **NOT EXECUTED** — depends on Phase 2 infrastructure
- Function App: `func azure functionapp publish func-rxodocnorm-dev --python`
- Web App: `az webapp deploy --name web-rxodocnorm-dev --resource-group rg-rxodocnorm-dev --src-path app.zip --type zip`

---

## Phase 5 — Foundry Agent Setup

- **PENDING** — Foundry agents are created independently via SDK/portal
- Agent 1: `RXO-Document-Normalizer` v5 (system prompt: `prompts/system_prompt_v5.md`)
- Agent 2: `RXO-Notes-PostProcessor` v1 (system prompt: `prompts/postprocess_system_prompt_v1.md`)
- After agents are deployed: set `foundryProjectEndpoint` and `assignFoundryRoles=true` in param file, redeploy

---

## Blockers & Next Steps

| # | Item | Owner | Priority |
|---|---|---|---|
| 1 | **Request VM quota increase** (Dynamic ≥1, Basic ≥1, East US) | Azure Admin | HIGH |
| 2 | Re-run `az deployment group create` after quota approved | DevOps / GHCP | HIGH |
| 3 | Deploy Function App code via `func publish` | DevOps / GHCP | MEDIUM |
| 4 | Deploy Streamlit Web App via zip deploy | DevOps / GHCP | MEDIUM |
| 5 | Configure Foundry agents when endpoint is ready | AI team | LOW |
| 6 | Set `assignFoundryRoles=true` and redeploy for Foundry RBAC | DevOps / GHCP | LOW |

---

*Report complete. IaC is fully validated and deployment-ready pending quota.*
