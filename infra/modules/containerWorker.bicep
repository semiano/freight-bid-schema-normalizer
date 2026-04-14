@description('Whether to create optional sandbox worker resources.')
param enabled bool = false

@description('Name prefix for optional worker resources.')
param namePrefix string = 'rxo-worker'

@description('Azure region for optional worker resources.')
param location string = resourceGroup().location

@description('Container image for the optional execution worker job.')
param workerImage string = 'mcr.microsoft.com/k8se/quickstart-jobs:latest'

@description('CPU cores for the optional execution worker container job.')
param workerCpu int = 1

@description('Memory allocation for the optional execution worker container job.')
param workerMemory string = '2Gi'

@description('Max runtime in seconds per worker job execution replica.')
param replicaTimeoutSeconds int = 1200

@description('Max retry count per worker job execution replica.')
param replicaRetryLimit int = 1

@description('Non-secret environment variables for the optional worker container.')
param workerEnvironmentVariables object = {}

@description('Tags applied to optional worker resources.')
param tags object = {}

var managedEnvironmentName = toLower(take('${namePrefix}-env', 60))
var workerJobName = toLower(take('${namePrefix}-job', 63))
var containerEnvironmentVariables = [for item in items(workerEnvironmentVariables): {
	name: item.key
	value: string(item.value)
}]

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = if (enabled) {
	name: managedEnvironmentName
	location: location
	tags: tags
	properties: {}
}

resource workerJob 'Microsoft.App/jobs@2024-03-01' = if (enabled) {
	name: workerJobName
	location: location
	tags: tags
	identity: {
		type: 'SystemAssigned'
	}
	properties: {
		environmentId: managedEnvironment.id
		configuration: {
			triggerType: 'Manual'
			replicaTimeout: replicaTimeoutSeconds
			replicaRetryLimit: replicaRetryLimit
			manualTriggerConfig: {
				parallelism: 1
				replicaCompletionCount: 1
			}
		}
		template: {
			containers: [
				{
					name: 'worker'
					image: workerImage
					env: containerEnvironmentVariables
					resources: {
						cpu: workerCpu
						memory: workerMemory
					}
				}
			]
		}
	}
}

output workerEnabled bool = enabled
output workerName string = workerJob.?name ?? ''
output workerLocation string = location
output workerTags object = tags
output workerManagedEnvironmentId string = managedEnvironment.?id ?? ''
output workerJobResourceId string = workerJob.?id ?? ''
output workerPrincipalId string = workerJob.?identity.?principalId ?? ''
