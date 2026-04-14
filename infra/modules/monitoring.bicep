@description('Base name used to build resource names.')
param baseName string

@description('Deployment environment name (dev, test, prod).')
param environmentName string

@description('Azure region for resources.')
param location string

@description('Retention period in days for Log Analytics.')
param workspaceRetentionInDays int = 30

@description('Tags applied to monitoring resources.')
param tags object = {}

var workspaceName = take('log-${baseName}-${environmentName}', 63)
var appInsightsName = take('appi-${baseName}-${environmentName}', 260)

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: workspaceRetentionInDays
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

output workspaceId string = logAnalytics.id
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsName string = appInsights.name
