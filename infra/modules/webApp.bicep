@description('Base name used to build resource names.')
param baseName string

@description('Deployment environment name (dev, test, prod).')
param environmentName string

@description('Azure region for resources.')
param location string

@description('App Service plan resource ID to host the web app.')
param planId string

@description('Storage account name for blob access from the Streamlit UI.')
param storageAccountName string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Foundry project endpoint for agents page status display.')
param foundryProjectEndpoint string = ''

@description('The Function App default hostname the UI will query.')
param functionAppHostname string = ''

@description('Startup command for the Streamlit container.')
param startupCommand string = 'python -m streamlit run streamlit_app.py --server.port 8000 --server.address 0.0.0.0'

@description('Tags applied to the Web App.')
param tags object = {}

var webAppName = toLower(take(replace('web-${baseName}-${environmentName}', '_', '-'), 60))

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: planId
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appCommandLine: startupCommand
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
        {
          name: 'FOUNDRY_PROJECT_ENDPOINT'
          value: foundryProjectEndpoint
        }
        {
          name: 'FUNCTION_APP_HOSTNAME'
          value: functionAppHostname
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
      ]
    }
  }
}

output webAppId string = webApp.id
output webAppName string = webApp.name
output principalId string = webApp.identity.principalId
output defaultHostname string = webApp.properties.defaultHostName
