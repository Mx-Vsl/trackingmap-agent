# Azure deployment script for TrackingMap Agent
# This script deploys the backend service, SQL database, and frontend to Azure

param(
    [string]$ResourceGroupName = "rg-trackingmap",
    [string]$Location = "West Europe",
    [string]$SqlAdminPassword = "ChangeThisPassword123!"  # Change this to a secure password
)

# Colors for output (PowerShell)
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"

Write-Host "Starting Azure deployment for TrackingMap Agent..." -ForegroundColor $Green

# Check if Azure CLI is installed
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "Azure CLI is not installed. Please install it first: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor $Red
    exit 1
}

# Login to Azure (uncomment if needed)
# Write-Host "Please login to Azure..." -ForegroundColor $Yellow
# az login

# Create resource group
Write-Host "Creating resource group: $ResourceGroupName" -ForegroundColor $Yellow
az group create --name $ResourceGroupName --location $Location

# Set environment variable for Bicep parameters
$env:SQL_ADMIN_PASSWORD = $SqlAdminPassword

# Deploy infrastructure using Bicep
Write-Host "Deploying infrastructure with Bicep..." -ForegroundColor $Yellow
az deployment group create `
  --resource-group $ResourceGroupName `
  --template-file main.bicep `
  --parameters main.bicepparam

# Get deployment outputs
$backendUrl = az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.backendAppServiceUrl.value -o tsv
$frontendUrl = az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.frontendAppServiceUrl.value -o tsv

Write-Host "Infrastructure deployed successfully!" -ForegroundColor $Green
Write-Host "Backend URL: $backendUrl" -ForegroundColor $Green
Write-Host "Frontend URL: $frontendUrl" -ForegroundColor $Green

# Create deployment package for backend
Write-Host "Creating deployment package for backend..." -ForegroundColor $Yellow
New-Item -ItemType Directory -Force -Path deployment/backend
Copy-Item -Path src -Destination deployment/backend/ -Recurse
Copy-Item requirements.txt deployment/backend/
Copy-Item pyproject.toml deployment/backend/

# Create startup script for backend
@"
#!/bin/bash
cd /home/site/wwwroot
python -m pip install -r requirements.txt
python -c "import trackingmap_agent.tracker_db; trackingmap_agent.tracker_db.init_db(use_azure_sql=True)"
"@ | Out-File -FilePath deployment/backend/startup.sh -Encoding UTF8

# Deploy backend using zip deployment
Write-Host "Deploying backend application..." -ForegroundColor $Yellow
Compress-Archive -Path deployment/backend/* -DestinationPath deployment/backend.zip -Force
az webapp deployment source config-zip `
  --resource-group $ResourceGroupName `
  --name trackingmap-backend `
  --src deployment/backend.zip

# Create deployment package for frontend
Write-Host "Creating deployment package for frontend..." -ForegroundColor $Yellow
New-Item -ItemType Directory -Force -Path deployment/frontend
Copy-Item map_app.py deployment/frontend/
Copy-Item requirements.txt deployment/frontend/

# Deploy frontend
Write-Host "Deploying frontend application..." -ForegroundColor $Yellow
Compress-Archive -Path deployment/frontend/* -DestinationPath deployment/frontend.zip -Force
az webapp deployment source config-zip `
  --resource-group $ResourceGroupName `
  --name trackingmap-frontend `
  --src deployment/frontend.zip

Write-Host "Deployment completed successfully!" -ForegroundColor $Green
Write-Host "Backend URL: $backendUrl" -ForegroundColor $Green
Write-Host "Frontend URL: $frontendUrl" -ForegroundColor $Green
Write-Host "Don't forget to set your TTN environment variables in the App Services!" -ForegroundColor $Yellow