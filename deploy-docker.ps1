# Docker Container Deployment to Azure
# This script builds Docker images and deploys to Azure Container Instances

param(
    [string]$ResourceGroupName = "rg-trackingmap",
    [string]$Location = "East US",
    [string]$AcrName = "acrtrackingmap",
    [string]$BackendContainerName = "aci-backend-trackingmap",
    [string]$FrontendContainerName = "aci-frontend-trackingmap",
    [string]$SqlAdminPassword = "rosskur-26!admin"
)

# Colors for output (PowerShell)
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"

Write-Host "🚀 Starting Docker Container Deployment to Azure..." -ForegroundColor $Green

# Check if Docker is installed
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor $Red
    exit 1
}

# Check if Azure CLI is installed
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it first." -ForegroundColor $Red
    exit 1
}

# Login to Azure (if not already logged in)
Write-Host "🔐 Checking Azure login..." -ForegroundColor $Yellow
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Please login to Azure..." -ForegroundColor $Yellow
    az login
}

# Create resource group
Write-Host "📁 Creating resource group: $ResourceGroupName" -ForegroundColor $Yellow
az group create --name $ResourceGroupName --location $Location

# Create Azure Container Registry
Write-Host "🏗️ Creating Azure Container Registry: $AcrName" -ForegroundColor $Yellow
az acr create --resource-group $ResourceGroupName --name $AcrName --sku Basic

# Login to ACR
Write-Host "🔑 Logging into Azure Container Registry..." -ForegroundColor $Yellow
az acr login --name $AcrName

# Get ACR login server
$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv

# Build and push backend image
Write-Host "🏗️ Building backend Docker image..." -ForegroundColor $Yellow
docker build -f Dockerfile.backend -t "$($acrLoginServer)/trackingmap-backend:latest" .

Write-Host "📤 Pushing backend image to ACR..." -ForegroundColor $Yellow
docker push "$($acrLoginServer)/trackingmap-backend:latest"

# Build and push frontend image
Write-Host "🏗️ Building frontend Docker image..." -ForegroundColor $Yellow
docker build -f Dockerfile.frontend -t "$($acrLoginServer)/trackingmap-frontend:latest" .

Write-Host "📤 Pushing frontend image to ACR..." -ForegroundColor $Yellow
docker push "$($acrLoginServer)/trackingmap-frontend:latest"

# Create backend container instance
Write-Host "🚀 Deploying backend container instance..." -ForegroundColor $Yellow
az container create `
    --resource-group $ResourceGroupName `
    --name $BackendContainerName `
    --image "$($acrLoginServer)/trackingmap-backend:latest" `
    --cpu 1 `
    --memory 1.5 `
    --registry-login-server $acrLoginServer `
    --registry-username $(az acr credential show --name $AcrName --query username -o tsv) `
    --registry-password $(az acr credential show --name $AcrName --query passwords[0].value -o tsv) `
    --environment-variables USE_AZURE_SQL=false `
    --ports 8000 `
    --restart-policy Always

# Create frontend container instance
Write-Host "🚀 Deploying frontend container instance..." -ForegroundColor $Yellow
az container create `
    --resource-group $ResourceGroupName `
    --name $FrontendContainerName `
    --image "$($acrLoginServer)/trackingmap-frontend:latest" `
    --cpu 1 `
    --memory 1.5 `
    --registry-login-server $acrLoginServer `
    --registry-username $(az acr credential show --name $AcrName --query username -o tsv) `
    --registry-password $(az acr credential show --name $AcrName --query passwords[0].value -o tsv) `
    --environment-variables USE_AZURE_SQL=false `
    --ports 8501 `
    --restart-policy Always

# Get container instance IPs
Write-Host "📋 Getting container instance details..." -ForegroundColor $Yellow
$backendIp = az container show --resource-group $ResourceGroupName --name $BackendContainerName --query ipAddress.ip -o tsv
$frontendIp = az container show --resource-group $ResourceGroupName --name $FrontendContainerName --query ipAddress.ip -o tsv

Write-Host "✅ Deployment completed successfully!" -ForegroundColor $Green
Write-Host "🌐 Backend URL: http://$backendIp:8000" -ForegroundColor $Green
Write-Host "🌐 Frontend URL: http://$frontendIp:8501" -ForegroundColor $Green
Write-Host "⚠️ Don't forget to set your TTN environment variables!" -ForegroundColor $Yellow
Write-Host "💡 Use: az container exec --resource-group $ResourceGroupName --name $BackendContainerName --exec-command 'env'" -ForegroundColor $Yellow