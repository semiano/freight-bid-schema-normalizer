using './main.bicep'

param environmentName = 'prod'
param location = 'eastus'
param baseName = 'rxodocnorm'
param tags = {
  app: 'rxo-document-normalizer'
  environment: 'prod'
  owner: 'rxo-data-platform'
  criticality: 'high'
}

param storageSkuName = 'Standard_GRS'
param workspaceRetentionInDays = 90

param functionPlanSkuName = 'FC1'
param functionPlanSkuTier = 'FlexConsumption'

param plannerMode = 'live'
param runMode = 'execute_with_validation'

param foundryProjectEndpoint = ''
param foundryAgentName = 'RXO-Document-Normalizer'
param foundryAgentVersion = '5'
param foundryAssistantId = ''

param foundryPostProcessAgentName = 'RXO-Notes-PostProcessor'
param foundryPostProcessAgentVersion = '1'
param postprocessMode = 'live'

param foundryAccountName = ''
param foundryProjectName = 'proj-default'
param createFoundryProject = false
param assignFoundryRoles = false

param enableWebApp = false
param webAppPlanSkuName = 'F1'
param webAppPlanSkuTier = 'Free'

param enableStreamlitContainerApp = true
param acrLoginServer = 'rxodocnormacr.azurecr.io'
param streamlitContainerImage = 'streamlit-ui:v2'
