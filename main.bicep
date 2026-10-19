@description('Location for all resources.')
param location string = 'westeurope'

@description('Name of the SQL Server.')
param sqlServerName string

@description('Name of the SQL Database.')
param sqlDatabaseName string

@description('Administrator username for the SQL Server.')
@secure()
param sqlAdministratorLogin string

@description('Administrator password for the SQL Server.')
@secure()
param sqlAdministratorLoginPassword string

@description('Name of the App Service Plan for backend.')
param backendAppServicePlanName string

@description('Name of the backend App Service.')
param backendAppServiceName string

@description('Name of the App Service Plan for frontend.')
param frontendAppServicePlanName string

@description('Name of the frontend App Service.')
param frontendAppServiceName string

@description('Runtime stack for the applications.')
param runtimeStack string = 'python:3.9'

@description('SKU for App Service Plans.')
param appServicePlanSku string = 'D1'  // D1 = Shared tier (cost-effective for development)

// SQL Server
resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: sqlAdministratorLogin
    administratorLoginPassword: sqlAdministratorLoginPassword
    version: '12.0'
    publicNetworkAccess: 'Enabled'
  }
}

// SQL Database
resource sqlDatabase 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  sku: {
    name: 'Basic'  // Basic tier = cost-effective for development
    tier: 'Basic'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648 // 2 GB
    zoneRedundant: false
  }
}

// Firewall rule to allow Azure services
resource sqlFirewallRule 'Microsoft.Sql/servers/firewallRules@2022-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Backend App Service Plan
resource backendAppServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: backendAppServicePlanName
  location: location
  sku: {
    name: appServicePlanSku
    tier: appServicePlanSku
  }
  properties: {
    reserved: false
  }
}

// Backend App Service
resource backendAppService 'Microsoft.Web/sites@2022-03-01' = {
  name: backendAppServiceName
  location: location
  properties: {
    serverFarmId: backendAppServicePlan.id
    siteConfig: {
      linuxFxVersion: runtimeStack
      alwaysOn: true
      appSettings: [
        {
          name: 'USE_AZURE_SQL'
          value: 'true'
        }
        {
          name: 'AZURE_SQL_SERVER'
          value: sqlServer.properties.fullyQualifiedDomainName
        }
        {
          name: 'AZURE_SQL_DATABASE'
          value: sqlDatabaseName
        }
        {
          name: 'AZURE_SQL_USERNAME'
          value: sqlAdministratorLogin
        }
        {
          name: 'AZURE_SQL_PASSWORD'
          value: sqlAdministratorLoginPassword
        }
      ]
    }
  }
}

// Frontend App Service Plan
resource frontendAppServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: frontendAppServicePlanName
  location: location
  sku: {
    name: appServicePlanSku
    tier: appServicePlanSku
  }
  properties: {
    reserved: false
  }
}

// Frontend App Service
resource frontendAppService 'Microsoft.Web/sites@2022-03-01' = {
  name: frontendAppServiceName
  location: location
  properties: {
    serverFarmId: frontendAppServicePlan.id
    siteConfig: {
      linuxFxVersion: runtimeStack
      alwaysOn: true
      appSettings: [
        {
          name: 'USE_AZURE_SQL'
          value: 'true'
        }
        {
          name: 'AZURE_SQL_SERVER'
          value: sqlServer.properties.fullyQualifiedDomainName
        }
        {
          name: 'AZURE_SQL_DATABASE'
          value: sqlDatabaseName
        }
        {
          name: 'AZURE_SQL_USERNAME'
          value: sqlAdministratorLogin
        }
        {
          name: 'AZURE_SQL_PASSWORD'
          value: sqlAdministratorLoginPassword
        }
      ]
    }
  }
}

// Outputs
output sqlServerName string = sqlServer.name
output sqlDatabaseName string = sqlDatabase.name
output backendAppServiceUrl string = 'https://${backendAppService.name}.azurewebsites.net'
output frontendAppServiceUrl string = 'https://${frontendAppService.name}.azurewebsites.net'
