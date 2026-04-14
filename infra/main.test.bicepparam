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
param foundryAgentVersion = '3'
param foundryAssistantId = ''

param foundryAccountName = ''
param foundryProjectName = 'proj-default'
param createFoundryProject = false
param assignFoundryRoles = false
