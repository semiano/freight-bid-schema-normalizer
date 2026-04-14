@description('Base name used to build resource names.')
param baseName string

@description('Deployment environment name (dev, test, prod).')
param environmentName string

@description('Azure region for resources.')
param location string

@description('App Service plan SKU name (Y1 for consumption).')
param skuName string = 'Y1'

@description('App Service plan SKU tier.')
param skuTier string = 'Dynamic'

@description('Tags applied to the plan.')
param tags object = {}

var functionPlanName = take('plan-${baseName}-${environmentName}', 40)

resource functionPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    reserved: true
  }
}

output planId string = functionPlan.id
output planName string = functionPlan.name
