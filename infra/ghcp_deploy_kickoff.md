# GHCP Kick-Off Prompt: Bicep Deployment & RBAC Configuration

> **Purpose**: This prompt is designed to be given to GitHub Copilot (or a human DevOps
> engineer) to deploy the RXO Document Normalizer infrastructure end-to-end and verify
> that every RBAC role assignment is correctly in place.
>
> **Prerequisites**: Azure CLI authenticated (`az login`), Bicep CLI available,
> target subscription selected, resource group created.

---

## Prompt

```text
You are deploying the RXO Document Normalizer platform to Azure. The IaC lives under
infra/ and uses Bicep with parameterized environments (dev / test / prod). Follow every
step below IN ORDER and report results at each gate before proceeding.

IMPORTANT ARCHITECTURE NOTES:
- Function App runs on FlexConsumption (FC1) — NOT Dynamic/Y1 (subscription has zero VM quota)
- Streamlit UI runs on Azure Container Apps — NOT Web App (zero VM quota for any App Service SKU)
- ACR (rxodocnormacr.azurecr.io) hosts the Streamlit Docker image
- All storage access uses managed identity (no connection strings in production)
- ACR credentials are passed as --parameters overrides, NEVER stored in param files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — PRE-FLIGHT VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1.1  Compile every Bicep file and confirm 0 errors / 0 warnings:
       infra/main.bicep
       infra/modules/storage.bicep
       infra/modules/functionApp.bicep
       infra/modules/functionPlan.bicep
       infra/modules/keyVault.bicep
       infra/modules/monitoring.bicep
       infra/modules/roles.bicep
       infra/modules/containerWorker.bicep
       infra/modules/webApp.bicep
       infra/modules/streamlitApp.bicep

     Command per file:
       az bicep build --file <path> --stdout > NUL

1.2  Validate all three .bicepparam files parse cleanly against main.bicep:
       infra/main.dev.bicepparam
       infra/main.test.bicepparam
       infra/main.prod.bicepparam

1.3  Confirm the param files supply these REQUIRED values for each environment:
       - environmentName                         (dev | test | prod)
       - enableWebApp                            = false  (VM quota is zero)
       - enableStreamlitContainerApp             = true
       - acrLoginServer                          = 'rxodocnormacr.azurecr.io'
  - streamlitContainerImage                 (e.g. 'streamlit-ui:<tag>')
       - foundryAgentVersion                     (must be "5")
       - foundryPostProcessAgentName             = "RXO-Notes-PostProcessor"
       - foundryPostProcessAgentVersion          = "1"
       - postprocessMode                         (mock for dev/test, live for prod)

     GATE: Print a table of env → param → value for the above params.
           Abort if any value is missing or incorrect.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — DEPLOY INFRASTRUCTURE  (target: dev by default)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  Set target environment (default dev unless told otherwise):
       ENV=dev
       RG=rg-rxodocnorm-$ENV

2.2  Create the resource group if it doesn't exist:
       az group create --name $RG --location eastus

2.3  Run a what-if dry run first (NO actual deploy):
       az deployment group what-if \
         --resource-group $RG \
         --template-file infra/main.bicep \
         --parameters infra/main.${ENV}.bicepparam \
         --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
                     acrUsername='<acr-admin-user>' \
                     acrPassword='<acr-admin-password>'

     GATE: Review the what-if output. Confirm it creates:
       ✓ Storage account with 4 containers (input, output, artifacts, deploymentpackage)
       ✓ Log Analytics workspace + Application Insights
       ✓ Key Vault (RBAC-authorized)
       ✓ FlexConsumption (FC1) App Service plan
       ✓ Function App (Linux Python 3.12, system MI, FC1 config)
       ✓ Container Apps managed environment + Streamlit Container App
       ✓ 4+ RBAC role assignments (blob data owner, KV secrets user,
           blob data contributor for Streamlit, etc.)
       ✗ Web App = disabled (enableWebApp=false, VM quota is zero)
         ✗ Container Worker = disabled (no additional worker resources)
       ✗ Foundry project = not created (createFoundryProject=false)

     Report any unexpected creates, deletes, or modifications.

2.4  If what-if is clean, execute the real deployment:
       az deployment group create \
         --resource-group $RG \
         --parameters infra/main.${ENV}.bicepparam \
         --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
                     acrUsername='<acr-admin-user>' \
                     acrPassword='<acr-admin-password>'

     GATE: Capture and report these outputs:
       - functionAppName
       - storageAccountName
       - keyVaultUri
       - streamlitAppName
       - streamlitFqdn
       - functionPrincipalId
       - streamlitPrincipalId

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — RBAC VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Refer to infra/rbac_assignments.md for the complete role matrix.

3.1  Retrieve managed identity principal IDs:

       FUNC_PRINCIPAL=$(az functionapp identity show \
         --name func-rxodocnorm-$ENV \
         --resource-group $RG \
         --query principalId -o tsv)

       STREAMLIT_PRINCIPAL=$(az containerapp show \
         --name rxodocnorm-streamlit-$ENV-app \
         --resource-group $RG \
         --query identity.principalId -o tsv)

3.2  List all role assignments for each identity:
       az role assignment list --assignee-object-id "$FUNC_PRINCIPAL" --all -o table
       az role assignment list --assignee-object-id "$STREAMLIT_PRINCIPAL" --all -o table

3.3  Validate against the checklist (print PASS/FAIL for each):

     Function App:
       [ ] Storage Blob Data Owner on storage account
       [ ] Key Vault Secrets User on Key Vault
       [ ] (if assignFoundryRoles=true) Cognitive Services OpenAI User on Foundry account
       [ ] (if assignFoundryRoles=true) Azure AI User on Foundry project
       [ ] (if cross-RG manual RBAC) Azure AI Developer on Foundry account

     Streamlit Container App:
       [ ] Storage Blob Data Contributor on storage account
       [ ] (if assignFoundryRoles=true) Cognitive Services OpenAI User on Foundry account
       [ ] (if assignFoundryRoles=true) Azure AI User on Foundry project
       [ ] (if cross-RG manual RBAC) Azure AI Developer on Foundry account

     GATE: ALL required roles must show PASS.
           If any show FAIL, diagnose and fix before proceeding.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — APPLICATION DEPLOYMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4.1  Deploy Function App code:
       func azure functionapp publish func-rxodocnorm-$ENV --python

4.2  Rebuild and push Streamlit image to ACR (if code changed):
       az acr build --registry rxodocnormacr \
         --image streamlit-ui:<tag> \
         --file Dockerfile.streamlit . --no-logs

       # Then update the Container App with the new image (fast path):
       az containerapp update \
         --name rxodocnorm-streamlit-$ENV-app \
         --resource-group $RG \
         --image rxodocnormacr.azurecr.io/streamlit-ui:<tag>

       # Or keep image tag in IaC state by redeploying Bicep:
       az deployment group create \
         --resource-group $RG \
         --parameters infra/main.${ENV}.bicepparam \
         --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
                     acrUsername='<acr-admin-user>' \
                     acrPassword='<acr-admin-password>' \
                     streamlitContainerImage='streamlit-ui:<tag>'

4.3  Smoke tests:
       # Function App health
       curl -s https://func-rxodocnorm-$ENV.azurewebsites.net/api/health | jq .

       # Streamlit Container App
       curl -s -o /dev/null -w "%{http_code}" \
         https://$(az containerapp show --name rxodocnorm-streamlit-$ENV-app \
           --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv)

     Expected: Function returns JSON with status; Streamlit returns 200.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — FOUNDRY AGENT CREATION & ENV VAR BACK-UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Foundry agents are data-plane objects — NOT provisioned by Bicep.
They are created via Python scripts, then the resulting config
values are pushed back into the Bicep deployment as env vars.

See infra/rbac_assignments.md §3 for detailed walkthrough.

5.1  PREREQUISITE: Ensure Foundry RBAC is enabled.

  If Foundry is in the SAME resource group as deployment, redeploy with:

       az deployment group create \
         --resource-group $RG \
         --parameters infra/main.${ENV}.bicepparam \
         --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
                     acrUsername='<acr-admin-user>' \
                     acrPassword='<acr-admin-password>' \
                     foundryProjectEndpoint='<FOUNDRY_ENDPOINT>' \
                     assignFoundryRoles=true \
                     foundryAccountName='<foundry-account-name>'

     If Foundry is in a DIFFERENT resource group, keep `assignFoundryRoles=false`
     and assign roles manually on the Foundry account scope:

       FOUNDRY_ID=$(az cognitiveservices account show -n <foundry-account-name> -g <foundry-rg> --query id -o tsv)
       FUNC_MI=$(az functionapp identity show -n func-rxodocnorm-$ENV -g $RG --query principalId -o tsv)
       STREAMLIT_MI=$(az containerapp identity show -n rxodocnorm-streamlit-$ENV-app -g $RG --query principalId -o tsv)

       for MI in $FUNC_MI $STREAMLIT_MI; do
         az role assignment create --assignee $MI --role "Cognitive Services OpenAI User" --scope $FOUNDRY_ID
         az role assignment create --assignee $MI --role "Azure AI User"                  --scope $FOUNDRY_ID
         az role assignment create --assignee $MI --role "Azure AI Developer"             --scope $FOUNDRY_ID
       done

     GATE: Confirm Foundry RBAC roles are assigned (Phase 3 checklist).

5.2  Create Transform Planner agent:

       export FOUNDRY_PROJECT_ENDPOINT="<FOUNDRY_ENDPOINT>"
       export FOUNDRY_AGENT_NAME="RXO-Document-Normalizer"
       export FOUNDRY_AGENT_VERSION="5"

       python scripts/deploy-foundry-agent.py --dry-run
       python scripts/deploy-foundry-agent.py --bump-version

     Expected output: "Created version: 5"

     NOTE: If agent doesn't exist yet, create it first in the
     Azure AI Foundry portal. The script adds versions to an
     existing agent.

5.3  Create Notes Post-Processor agent:

       export FOUNDRY_POSTPROCESS_AGENT_NAME="RXO-Notes-PostProcessor"
       export FOUNDRY_POSTPROCESS_AGENT_VERSION="1"

       python scripts/deploy-postprocess-agent.py --dry-run
       python scripts/deploy-postprocess-agent.py --bump-version

     Expected output: "Created version: 1"
     (This script can create the agent implicitly if it doesn't exist.)

5.4  (Optional) Capture assistant IDs if needed for Assistants API fallback:

       python -c "
       import os
       from azure.ai.projects import AIProjectClient
       from azure.identity import DefaultAzureCredential
       client = AIProjectClient(
           endpoint=os.environ['FOUNDRY_PROJECT_ENDPOINT'],
           credential=DefaultAzureCredential()
       )
       for a in client.agents.list():
           print(f'{a.name:40s} id={a.id}')
       "

     If an assistant_id is needed, note it for step 5.5.

5.5  BACK-UPDATE: Redeploy Bicep with agent config values.
     This pushes FOUNDRY_* env vars into both the Function App
     and Streamlit Container App simultaneously:

       az deployment group create \
         --resource-group $RG \
         --parameters infra/main.${ENV}.bicepparam \
         --parameters acrLoginServer='rxodocnormacr.azurecr.io' \
                     acrUsername='<acr-admin-user>' \
                     acrPassword='<acr-admin-password>' \
                     foundryProjectEndpoint='<FOUNDRY_ENDPOINT>' \
                     foundryAgentName='RXO-Document-Normalizer' \
                     foundryAgentVersion='5' \
                     foundryAssistantId='' \
                     foundryPostProcessAgentName='RXO-Notes-PostProcessor' \
                     foundryPostProcessAgentVersion='1' \
                     assignFoundryRoles=true \
                     foundryAccountName='<foundry-account-name>' \
                     plannerMode='live' \
                     postprocessMode='live'

     GATE: Verify env vars propagated to both services:

       # Function App
       az functionapp config appsettings list \
         --name func-rxodocnorm-$ENV \
         --resource-group $RG \
         --query "[?name=='FOUNDRY_PROJECT_ENDPOINT'].value" -o tsv

       # Container App
       az containerapp show \
         --name rxodocnorm-streamlit-$ENV-app \
         --resource-group $RG \
         --query "properties.template.containers[0].env[?name=='FOUNDRY_PROJECT_ENDPOINT'].value" \
         -o tsv

     Both must return the real Foundry endpoint URL.

5.6  Verify agents are reachable from the Streamlit UI:
     Open the Streamlit app → System Agents page.
     Both agents should show with ✅ status and correct version numbers.

     If "Could not query Foundry" still appears, the Container App
     may need a restart:
       az containerapp revision restart \
         --name rxodocnorm-streamlit-$ENV-app \
         --resource-group $RG \
         --revision $(az containerapp revision list \
           --name rxodocnorm-streamlit-$ENV-app \
           --resource-group $RG --query "[0].name" -o tsv)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 6 — FINAL DEPLOYMENT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generate a summary table with:

| Item                            | Value                              | Status |
|---------------------------------|-------------------------------------|--------|
| Resource Group                  | rg-rxodocnorm-{env}               | ✓/✗    |
| Storage Account                 | <name> (4 containers)              | ✓/✗    |
| Key Vault                       | <name>                             | ✓/✗    |
| Function App (FC1)              | <name> (principal: <id>)           | ✓/✗    |
| Streamlit Container App         | <name> (FQDN: <fqdn>)             | ✓/✗    |
| ACR                             | rxodocnormacr.azurecr.io           | ✓/✗    |
| Blob Data Owner (Func)          | assigned                           | ✓/✗    |
| KV Secrets User (Func)          | assigned                           | ✓/✗    |
| Blob Data Contributor (Streamlit)| assigned                          | ✓/✗    |
| Foundry OpenAI User (Func)      | assigned / skipped                 | ✓/—    |
| Foundry AI User (Func)          | assigned / skipped                 | ✓/—    |
| Foundry AI Developer (Func)     | assigned / skipped                 | ✓/—    |
| Foundry OpenAI User (Streamlit) | assigned / skipped                 | ✓/—    |
| Foundry AI User (Streamlit)     | assigned / skipped                 | ✓/—    |
| Foundry AI Developer (Streamlit)| assigned / skipped                 | ✓/—    |
| Container Worker                | disabled                           | —      |
| Transform Planner Agent         | v5 deployed / pending              | ✓/⏳   |
| Notes Post-Processor Agent      | v1 deployed / pending              | ✓/⏳   |
| Function App health             | 200 OK                             | ✓/✗    |
| Streamlit health                | 200 OK                             | ✓/✗    |
| Env vars injected (Streamlit)   | 14 vars from Bicep                 | ✓/✗    |
```

---

## Notes for the executing agent

- **No secrets in source control.** Foundry endpoint, subscription ID, tenant ID,
  and principal object IDs live only in param overrides or pipeline secrets.
- **Incremental mode only.** Never use `--mode Complete` — it deletes resources not
  in the template.
- **Re-entrant.** Every phase can be re-run safely. RBAC assignments use deterministic
  `guid()` names so redeployment won't create duplicates.
- **Foundry is decoupled.** Phases 1–4 work without any Foundry configuration.
  Phase 5 is optional until the team is ready to go live with AI agents.
