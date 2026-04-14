@description('Principal ID of the managed identity receiving roles.')
param principalId string

@description('Optional worker principal ID receiving additional roles when enabled.')
param workerPrincipalId string = ''

@description('Storage account name in current resource group.')
param storageAccountName string

@description('Key vault name in current resource group.')
param keyVaultName string

@description('Whether queue data contributor role should be granted.')
param grantQueueRole bool = false

@description('Assign Foundry roles on account/project in this resource group.')
param assignFoundryRoles bool = false

@description('Whether storage/key vault (and optional queue) roles should be granted to workerPrincipalId.')
param assignWorkerRoles bool = false

@description('Whether Foundry roles should be granted to workerPrincipalId.')
param assignWorkerFoundryRoles bool = false

@description('Foundry account name in current resource group.')
param foundryAccountName string = ''

@description('Foundry project name under the account.')
param foundryProjectName string = ''

var storageBlobDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var storageQueueDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
var keyVaultSecretsUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var openAiUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var azureAiUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
var shouldAssignWorkerRoles = assignWorkerRoles && !empty(workerPrincipalId)
var shouldAssignWorkerFoundryRoles = assignWorkerFoundryRoles && !empty(workerPrincipalId)

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (assignFoundryRoles && !empty(foundryAccountName)) {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = if (assignFoundryRoles && !empty(foundryAccountName) && !empty(foundryProjectName)) {
  name: foundryProjectName
  parent: foundryAccount
}

resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, principalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (grantQueueRole) {
  name: guid(storageAccount.id, principalId, storageQueueDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageQueueDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, principalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryAccountRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignFoundryRoles && !empty(foundryAccountName)) {
  name: guid(foundryAccount.id, principalId, openAiUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: openAiUserRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignFoundryRoles && !empty(foundryAccountName) && !empty(foundryProjectName)) {
  name: guid(foundryProject.id, principalId, azureAiUserRoleId)
  scope: foundryProject
  properties: {
    roleDefinitionId: azureAiUserRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerStorageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (shouldAssignWorkerRoles) {
  name: guid(storageAccount.id, workerPrincipalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerStorageQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (shouldAssignWorkerRoles && grantQueueRole) {
  name: guid(storageAccount.id, workerPrincipalId, storageQueueDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageQueueDataContributorRoleId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (shouldAssignWorkerRoles) {
  name: guid(keyVault.id, workerPrincipalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerFoundryAccountRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (shouldAssignWorkerFoundryRoles && !empty(foundryAccountName)) {
  name: guid(foundryAccount.id, workerPrincipalId, openAiUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: openAiUserRoleId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerFoundryProjectRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (shouldAssignWorkerFoundryRoles && !empty(foundryAccountName) && !empty(foundryProjectName)) {
  name: guid(foundryProject.id, workerPrincipalId, azureAiUserRoleId)
  scope: foundryProject
  properties: {
    roleDefinitionId: azureAiUserRoleId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output rolesAssigned bool = true
