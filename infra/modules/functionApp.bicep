@description('Base name used to build resource names.')
param baseName string

@description('Deployment environment name (dev, test, prod).')
param environmentName string

@description('Azure region for resources.')
param location string

@description('App Service plan resource ID.')
param planId string

@description('Storage connection string for AzureWebJobsStorage.')
@secure()
param storageConnectionString string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Key Vault URI.')
param keyVaultUri string

@description('Input blob container name.')
param inputContainer string = 'input'

@description('Output blob container name.')
param outputContainer string = 'output'

@description('Artifact blob container name.')
param artifactContainer string = 'artifacts'

@description('Additional app settings merged into base Function app settings.')
param additionalAppSettings object = {}

@description('Tags applied to the Function App.')
param tags object = {}

var functionAppName = toLower(take(replace('func-${baseName}-${environmentName}', '_', '-'), 60))
var baseSettings = [
  {
    name: 'FUNCTIONS_WORKER_RUNTIME'
    value: 'python'
  }
  {
    name: 'FUNCTIONS_EXTENSION_VERSION'
    value: '~4'
  }
  {
    name: 'AzureWebJobsStorage'
    value: storageConnectionString
  }
  {
    name: 'WEBSITE_RUN_FROM_PACKAGE'
    value: '1'
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: appInsightsConnectionString
  }
  {
    name: 'INPUT_CONTAINER'
    value: inputContainer
  }
  {
    name: 'OUTPUT_CONTAINER'
    value: outputContainer
  }
  {
    name: 'FUNCTION_PERSIST_ARTIFACTS'
    value: 'true'
  }
  {
    name: 'ARTIFACT_STORAGE_MODE'
    value: 'blob'
  }
  {
    name: 'ARTIFACT_BLOB_CONTAINER'
    value: artifactContainer
  }
  {
    name: 'KEY_VAULT_URI'
    value: keyVaultUri
  }
]
var customSettings = [for item in items(additionalAppSettings): {
  name: item.key
  value: string(item.value)
}]

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: planId
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: concat(baseSettings, customSettings)
    }
  }
}

output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output principalId string = functionApp.identity.principalId
