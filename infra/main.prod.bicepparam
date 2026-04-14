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

param functionPlanSkuName = 'Y1'
param functionPlanSkuTier = 'Dynamic'

param plannerMode = 'live'
param runMode = 'execute_with_validation'

param foundryProjectEndpoint = ''
param foundryAgentName = 'RXO-Document-Normalizer'
param foundryAgentVersion = '3'
param foundryAssistantId = ''

param foundryAccountName = ''
param foundryProjectName = 'proj-default'
param createFoundryProject = false
param assignFoundryRoles = false
