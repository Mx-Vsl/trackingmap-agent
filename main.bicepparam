using './main.bicep'

param sqlServerName = 'sql-trackingmap'
param sqlDatabaseName = 'trackingmap'
param sqlAdministratorLogin = 'sqladmin'
param sqlAdministratorLoginPassword = readEnvironmentVariable('SQL_ADMIN_PASSWORD')
param backendAppServicePlanName = 'asp-backend-trackingmap'
param backendAppServiceName = 'web-backend-trackingmap'
param frontendAppServicePlanName = 'asp-frontend-trackingmap'
param frontendAppServiceName = 'web-frontend-trackingmap'
