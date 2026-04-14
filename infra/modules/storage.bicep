@description('Base name used to build resource names.')
param baseName string

@description('Deployment environment name (dev, test, prod).')
param environmentName string

@description('Azure region for resources.')
param location string

@description('Storage account SKU name.')
param skuName string = 'Standard_LRS'

@description('Blob container names to create.')
param containerNames array = [
  'input'
  'output'
  'artifacts'
]

@description('Whether queue resources should be created.')
param createQueues bool = false

@description('Queue names to create when createQueues is true.')
param queueNames array = []

@description('Tags applied to the storage account.')
param tags object = {}

var storageAccountName = 'st${take(uniqueString(resourceGroup().id, baseName, environmentName), 22)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  name: 'default'
  parent: storageAccount
}

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for containerName in containerNames: {
  name: containerName
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}]

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = if (createQueues) {
  name: 'default'
  parent: storageAccount
}

resource queues 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = [for queueName in (createQueues ? queueNames : []): {
  name: queueName
  parent: queueService
}]

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output primaryBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output primaryQueueEndpoint string = storageAccount.properties.primaryEndpoints.queue
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
