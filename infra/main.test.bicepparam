using './main.bicep'

param environmentName = 'test'
param location = 'eastus'
param baseName = 'rxodocnorm'
param tags = {
  app: 'rxo-document-normalizer'
  environment: 'test'
  owner: 'rxo-data-platform'
}

param plannerMode = 'live'
param runMode = 'execute_with_validation'

param foundryProjectEndpoint = ''
param foundryAgentName = 'RXO-Document-Normalizer'
param foundryAgentVersion = '5'
param foundryAssistantId = ''

param foundryPostProcessAgentName = 'RXO-Notes-PostProcessor'
param foundryPostProcessAgentVersion = '1'
param postprocessMode = 'mock'

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
