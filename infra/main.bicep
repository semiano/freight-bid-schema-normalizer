targetScope = 'resourceGroup'

@description('Base name used to build resource names.')
param baseName string = 'rxodocnorm'

@description('Deployment environment name.')
@allowed([
  'dev'
  'test'
  'prod'
])
param environmentName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Tags applied across resources.')
param tags object = {}

@description('Blob containers to create.')
param containerNames array = [
  'input'
  'output'
  'artifacts'
]

@description('Create queue resources.')
param createQueues bool = false

@description('Queue names to create if createQueues is true.')
param queueNames array = []

@description('Storage SKU name.')
param storageSkuName string = 'Standard_LRS'

@description('Log Analytics retention in days.')
param workspaceRetentionInDays int = 30

@description('Function plan SKU name.')
param functionPlanSkuName string = 'Y1'

@description('Function plan SKU tier.')
param functionPlanSkuTier string = 'Dynamic'

@description('Function run mode.')
@allowed([
  'draft'
  'execute_with_validation'
])
param runMode string = 'execute_with_validation'

@description('Planner mode for function app.')
@allowed([
  'mock'
  'live'
])
param plannerMode string = 'live'

@description('Foundry project endpoint used by runtime.')
param foundryProjectEndpoint string = ''

@description('Foundry agent name for New Foundry invocation.')
param foundryAgentName string = 'RXO-Document-Normalizer'

@description('Foundry agent version for New Foundry invocation.')
param foundryAgentVersion string = '3'

@description('Foundry API version used by runtime.')
param foundryApiVersion string = '2025-05-15-preview'

@description('Foundry model fallback name used by runtime client.')
param foundryModel string = 'gpt-4.1'

@description('Canonical schema template name.')
param canonicalSchemaName string = 'freight_bid_v1'

@description('Optional preconfigured Foundry assistant ID (left empty for strict New Foundry agent_reference mode).')
param foundryAssistantId string = ''

@description('Optional Foundry account name in this resource group.')
param foundryAccountName string = ''

@description('Optional Foundry project name under foundryAccountName.')
param foundryProjectName string = 'proj-default'

@description('Whether to create the Foundry project resource under an existing account.')
param createFoundryProject bool = false

@description('Whether to assign Foundry data-plane roles to the Function App identity.')
param assignFoundryRoles bool = false

@description('Whether to assign storage/key vault roles to the optional container worker identity.')
param assignContainerWorkerRoles bool = false

@description('Whether to assign Foundry data-plane roles to the optional container worker identity.')
param assignContainerWorkerFoundryRoles bool = false

@description('Enable optional container worker placeholder module.')
param enableContainerWorker bool = false

@description('Container image for optional execution worker job.')
param containerWorkerImage string = 'mcr.microsoft.com/k8se/quickstart-jobs:latest'

@description('CPU cores for optional execution worker job container.')
param containerWorkerCpu int = 1

@description('Memory allocation for optional execution worker job container.')
param containerWorkerMemory string = '2Gi'

@description('Max runtime in seconds for optional execution worker job replicas.')
param containerWorkerReplicaTimeoutSeconds int = 1200

@description('Max retry count for optional execution worker job replicas.')
param containerWorkerReplicaRetryLimit int = 1

@description('Non-secret environment variables for the optional execution worker container.')
param containerWorkerEnvironmentVariables object = {}

module storage './modules/storage.bicep' = {
  name: 'storage'
  params: {
    baseName: baseName
    environmentName: environmentName
    location: location
    skuName: storageSkuName
    containerNames: containerNames
    createQueues: createQueues
    queueNames: queueNames
    tags: tags
  }
}

module monitoring './modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    baseName: baseName
    environmentName: environmentName
    location: location
    workspaceRetentionInDays: workspaceRetentionInDays
    tags: tags
  }
}

module keyVault './modules/keyVault.bicep' = {
  name: 'keyvault'
  params: {
    baseName: baseName
    environmentName: environmentName
    location: location
    tenantId: subscription().tenantId
    tags: tags
  }
}

module functionPlan './modules/functionPlan.bicep' = {
  name: 'functionplan'
  params: {
    baseName: baseName
    environmentName: environmentName
    location: location
    skuName: functionPlanSkuName
    skuTier: functionPlanSkuTier
    tags: tags
  }
}

var artifactContainerName = contains(containerNames, 'artifacts') ? 'artifacts' : containerNames[0]
var inputContainerName = contains(containerNames, 'input') ? 'input' : containerNames[0]
var outputContainerName = contains(containerNames, 'output') ? 'output' : containerNames[0]

module functionApp './modules/functionApp.bicep' = {
  name: 'functionapp'
  params: {
    baseName: baseName
    environmentName: environmentName
    location: location
    planId: functionPlan.outputs.planId
    storageConnectionString: storage.outputs.connectionString
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: keyVault.outputs.keyVaultUri
    inputContainer: inputContainerName
    outputContainer: outputContainerName
    artifactContainer: artifactContainerName
    additionalAppSettings: {
      RUN_MODE: runMode
      PLANNER_MODE: plannerMode
      FOUNDRY_PROJECT_ENDPOINT: foundryProjectEndpoint
      FOUNDRY_AGENT_NAME: foundryAgentName
      FOUNDRY_AGENT_VERSION: foundryAgentVersion
      FOUNDRY_API_VERSION: foundryApiVersion
      FOUNDRY_MODEL: foundryModel
      FOUNDRY_ASSISTANT_ID: foundryAssistantId
      CANONICAL_SCHEMA_NAME: canonicalSchemaName
      AZURE_BLOB_API_VERSION: '2021-08-06'
      ENABLE_LLM_VALIDATION: 'false'
      MAX_SCRIPT_EXECUTION_SECONDS: '45'
      MAX_PROFILE_SAMPLE_ROWS: '25'
    }
    tags: tags
  }
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (createFoundryProject && !empty(foundryAccountName)) {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = if (createFoundryProject && !empty(foundryAccountName) && !empty(foundryProjectName)) {
  name: foundryProjectName
  parent: foundryAccount
  location: location
  properties: {
    displayName: foundryProjectName
    description: 'RXO Document Normalizer Foundry Project'
  }
}

module roles './modules/roles.bicep' = {
  name: 'roles'
  params: {
    principalId: functionApp.outputs.principalId
    workerPrincipalId: containerWorker.outputs.workerPrincipalId
    storageAccountName: storage.outputs.storageAccountName
    keyVaultName: keyVault.outputs.keyVaultName
    grantQueueRole: createQueues
    assignFoundryRoles: assignFoundryRoles
    assignWorkerRoles: assignContainerWorkerRoles
    assignWorkerFoundryRoles: assignContainerWorkerFoundryRoles
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
  }
}

module containerWorker './modules/containerWorker.bicep' = {
  name: 'containerworker'
  params: {
    enabled: enableContainerWorker
    namePrefix: 'worker-${baseName}-${environmentName}'
    location: location
    workerImage: containerWorkerImage
    workerCpu: containerWorkerCpu
    workerMemory: containerWorkerMemory
    replicaTimeoutSeconds: containerWorkerReplicaTimeoutSeconds
    replicaRetryLimit: containerWorkerReplicaRetryLimit
    workerEnvironmentVariables: containerWorkerEnvironmentVariables
    tags: tags
  }
}

output functionAppName string = functionApp.outputs.functionAppName
output functionAppId string = functionApp.outputs.functionAppId
output functionPrincipalId string = functionApp.outputs.principalId
output storageAccountName string = storage.outputs.storageAccountName
output storageBlobEndpoint string = storage.outputs.primaryBlobEndpoint
output keyVaultUri string = keyVault.outputs.keyVaultUri
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output foundryProjectResourceId string = createFoundryProject ? foundryProject.id : ''
output containerWorkerJobResourceId string = containerWorker.outputs.workerJobResourceId
output containerWorkerManagedEnvironmentId string = containerWorker.outputs.workerManagedEnvironmentId
output containerWorkerPrincipalId string = containerWorker.outputs.workerPrincipalId
