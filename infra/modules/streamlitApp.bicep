@description('Whether to create the Streamlit Container App resources.')
param enabled bool = true

@description('Name prefix for the Container App resources.')
param namePrefix string = 'rxo-streamlit'

@description('Azure region for the Container App resources.')
param location string = resourceGroup().location

@description('ACR login server (e.g. myacr.azurecr.io).')
param acrLoginServer string

@description('ACR admin username.')
@secure()
param acrUsername string

@description('ACR admin password.')
@secure()
param acrPassword string

@description('Container image including tag (e.g. streamlit-ui:v1).')
param containerImage string = 'streamlit-ui:v1'

@description('Storage account name for blob access from the Streamlit UI.')
param storageAccountName string = ''

@description('Foundry project endpoint for agents page status display.')
param foundryProjectEndpoint string = ''

@description('The Function App default hostname the UI will query.')
param functionAppHostname string = ''

@description('Input blob container name.')
param inputContainer string = 'input'

@description('Output blob container name.')
param outputContainer string = 'output'

@description('Additional environment variables (key/value object) merged into the container.')
param additionalEnvVars object = {}

@description('CPU cores for the Streamlit container.')
param cpu string = '0.5'

@description('Memory allocation for the Streamlit container.')
param memory string = '1Gi'

@description('Minimum number of replicas.')
param minReplicas int = 0

@description('Maximum number of replicas.')
param maxReplicas int = 1

@description('Tags applied to the Container App resources.')
param tags object = {}

var managedEnvironmentName = toLower(take('${namePrefix}-env', 60))
var containerAppName = toLower(take('${namePrefix}-app', 63))

var baseEnvVars = [
  { name: 'STORAGE_ACCOUNT_NAME', value: storageAccountName }
  { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
  { name: 'FUNCTION_APP_HOSTNAME', value: functionAppHostname }
  { name: 'INPUT_CONTAINER', value: inputContainer }
  { name: 'OUTPUT_CONTAINER', value: outputContainer }
]
var customEnvVars = [for item in items(additionalEnvVars): {
  name: item.key
  value: string(item.value)
}]
var allEnvVars = concat(baseEnvVars, customEnvVars)

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = if (enabled) {
  name: managedEnvironmentName
  location: location
  tags: tags
  properties: {}
}

resource streamlitApp 'Microsoft.App/containerApps@2024-03-01' = if (enabled) {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: true
      }
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
      ]
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'streamlit'
          image: '${acrLoginServer}/${containerImage}'
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: allEnvVars
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

output streamlitEnabled bool = enabled
output streamlitAppName string = streamlitApp.?name ?? ''
output streamlitFqdn string = streamlitApp.?properties.?configuration.?ingress.?fqdn ?? ''
output streamlitPrincipalId string = streamlitApp.?identity.?principalId ?? ''
output managedEnvironmentId string = managedEnvironment.?id ?? ''
