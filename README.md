# TBD Project Name


[![License](https://img.shields.io/badge/license-bsd-3.svg)](https://choosealicense.com/licenses/bsd-3-clause/) [![Repo Status](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

- [TBD Project Name](#tbd-project-name)
  - [Overview](#overview)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Azure Deployment](#azure-deployment)
    - [Prerequisites](#prerequisites)
    - [Quick Deployment](#quick-deployment)
    - [Manual Deployment](#manual-deployment)
    - [Cost Optimization](#cost-optimization)
    - [Environment Variables](#environment-variables)
  - [Map UI](#map-ui)
  - [Examples](#examples)
  - [SW Documentation](#sw-documentation)
  - [Used Libraries](#used-libraries)
  - [Issues, Ideas And Bugs](#issues-ideas-and-bugs)
  - [License](#license)
  - [Contribution](#contribution)

## Overview

This tool will connect to the The Things Network (TTN) via MQTT to collect informations from connected GPS Tracker (tested with SenseCAP Tracker T1000-B).
The latest location incl. the last way points and some addtional information will be shown on a map.

## Installation

```bash
git clone https://github.com/achim0x/trackermap.git
cd trackermap
pip install -r requirements.txt
pip install -e .
```

Create a `.env` file containing the credentials to access your TTN tenant. Use `.env.example` as a template:

```bash
copy .env.example .env
```

Open `.env` and set your TTN values:

```env
TTN_APP_ID=my-lora-app
TTN_TENANT=ttn
TTN_REGION=eu1
TTN_API_KEY=NNSXS.…
USE_AZURE_SQL=false
```

## Usage

### Option 1: Docker Compose

```powershell
docker compose up --build
```

Then open:

- Backend health: `http://localhost:8000/health`
- Frontend UI: `http://localhost:8501`

If you want to run the backend without real TTN credentials, add `DUMMY_MODE=true` to `.env` and restart:

```env
DUMMY_MODE=true
```

### Option 2: Direct Python

Activate the virtual environment and run:

```powershell
.\.venv\Scripts\Activate.ps1
$env:USE_AZURE_SQL='false'
$env:TTN_APP_ID='your-app-id'
$env:TTN_TENANT='ttn'
$env:TTN_REGION='eu1'
$env:TTN_API_KEY='your-api-key'
python -m trackingmap_agent
```

In another shell, start the frontend:

```powershell
streamlit run map_app.py
```

## Azure Deployment

This application can be deployed to Azure with a backend service, Azure SQL Database, and frontend UI.

### Prerequisites

- Azure CLI installed
- Azure subscription
- TTN (The Things Network) account and API key

### Quick Deployment

1. **Clone and prepare the repository:**
   ```bash
   git clone <repository-url>
   cd trackingmap-agent
   ```

2. **Run the deployment script:**
   ```powershell
   .\deploy.ps1 -SqlAdminPassword "YourSecurePassword123!"
   ```

   Or with custom parameters:
   ```powershell
   .\deploy.ps1 -ResourceGroupName "rg-trackingmap" -Location "West Europe" -SqlAdminPassword "YourSecurePassword123!"
   ```

3. **Configure TTN environment variables:**

   After deployment, set the TTN environment variables in both App Services:

   ```bash
   az webapp config appsettings set --name web-backend-trackingmap --resource-group rg-trackingmap --setting TTN_APP_ID="your-app-id" TTN_TENANT="ttn" TTN_REGION="eu1" TTN_API_KEY="your-api-key"
   az webapp config appsettings set --name web-frontend-trackingmap --resource-group rg-trackingmap --setting TTN_APP_ID="your-app-id" TTN_TENANT="ttn" TTN_REGION="eu1" TTN_API_KEY="your-api-key"
   ```

4. **Access your applications:**

   The deployment script will output the URLs for both the backend and frontend applications.

### Manual Deployment

If you prefer to deploy manually:

1. **Deploy infrastructure:**
   ```bash
   az group create --name rg-trackingmap --location "West Europe"
   az deployment group create --resource-group rg-trackingmap --template-file main.bicep --parameters main.bicepparam --parameters sqlAdministratorLoginPassword="YourPassword"
   ```

2. **Deploy applications:**
   - Create deployment packages and use `az webapp deployment source config-zip`

### Cost Optimization

**Azure Container Instances:**
- **Backend Container**: ~$15/month (1 vCPU, 1.5 GB RAM, always on)
- **Frontend Container**: ~$15/month (1 vCPU, 1.5 GB RAM, always on)
- **Azure Container Registry**: ~$5/month (Basic tier)
- **Total**: ~$35/month

**Previous App Service option:**
- **Backend App Service (D1)**: ~$10/month
- **Frontend App Service (D1)**: ~$10/month
- **Azure SQL Database (Basic)**: ~$5/month
- **Total**: ~$25/month

**For production use**, consider upgrading to higher CPU/memory or using Azure Container Apps for better scaling.

### Environment Variables

The following environment variables need to be set:

For both backend and frontend:
- `USE_AZURE_SQL=true`
- `AZURE_SQL_SERVER=<server-name>.database.windows.net`
- `AZURE_SQL_DATABASE=<database-name>`
- `AZURE_SQL_USERNAME=<admin-username>`
- `AZURE_SQL_PASSWORD=<admin-password>`

For backend only:
- `TTN_APP_ID=<your-ttn-app-id>`
- `TTN_TENANT=ttn`
- `TTN_REGION=<your-region>`
- `TTN_API_KEY=<your-api-key>`

## Docker Container Deployment

This application can be deployed as Docker containers to Azure Container Instances, avoiding regional restrictions.

### Prerequisites

- Docker Desktop installed
- Azure CLI installed
- Azure subscription

### Local Development

1. **Create .env file:**
   ```bash
   TTN_APP_ID=your-ttn-app-id
   TTN_TENANT=ttn
   TTN_REGION=eu1
   TTN_API_KEY=your-ttn-api-key
   ```

2. **Run locally with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

   Access:
   - Backend health check: http://localhost:8000/health
   - Frontend: http://localhost:8501

### Azure Container Instances Deployment

1. **Run the deployment script:**
   ```powershell
   .\deploy-docker.ps1 -SqlAdminPassword "YourSecurePassword123!"
   ```

   Or with custom parameters:
   ```powershell
   .\deploy-docker.ps1 -ResourceGroupName "rg-trackingmap" -Location "East US" -SqlAdminPassword "YourSecurePassword123!"
   ```

2. **Configure TTN environment variables:**
   ```bash
   # Set environment variables on the backend container
   az container exec --resource-group rg-trackingmap --name aci-backend-trackingmap --exec-command "export TTN_APP_ID=your-app-id"
   az container exec --resource-group rg-trackingmap --name aci-backend-trackingmap --exec-command "export TTN_TENANT=ttn"
   az container exec --resource-group rg-trackingmap --name aci-backend-trackingmap --exec-command "export TTN_REGION=eu1"
   az container exec --resource-group rg-trackingmap --name aci-backend-trackingmap --exec-command "export TTN_API_KEY=your-api-key"
   ```

### Manual Docker Deployment

1. **Build images:**
   ```bash
   docker build -f Dockerfile.backend -t trackingmap-backend .
   docker build -f Dockerfile.frontend -t trackingmap-frontend .
   ```

2. **Create Azure Container Registry:**
   ```bash
   az acr create --resource-group rg-trackingmap --name acrtrackingmap --sku Basic
   ```

3. **Push images:**
   ```bash
   az acr login --name acrtrackingmap
   docker tag trackingmap-backend acrtrackingmap.azurecr.io/trackingmap-backend:latest
   docker push acrtrackingmap.azurecr.io/trackingmap-backend:latest
   docker tag trackingmap-frontend acrtrackingmap.azurecr.io/trackingmap-frontend:latest
   docker push acrtrackingmap.azurecr.io/trackingmap-frontend:latest
   ```

4. **Deploy containers:**
   ```bash
   az container create --resource-group rg-trackingmap --name aci-backend-trackingmap --image acrtrackingmap.azurecr.io/trackingmap-backend:latest --cpu 1 --memory 1.5 --ports 8000 --restart-policy Always
   az container create --resource-group rg-trackingmap --name aci-frontend-trackingmap --image acrtrackingmap.azurecr.io/trackingmap-frontend:latest --cpu 1 --memory 1.5 --ports 8501 --restart-policy Always
   ```

## Map UI

To view the collected tracker data on a map, access the frontend URL provided after deployment.
```

This will start a web server at http://localhost:8501 where you can see all tracker locations with their names and timestamps.

## Examples

Check out the all the [Examples](./examples).

## SW Documentation

More information on the deployment and architecture can be found in the [documentation](./doc/README.md)

For Detailed Software Design run `$ /doc/detailed-design/make html` to generate the detailed design documentation that then can be found
in the folder `/doc/detailed-design/_build/html/index.html`

## Used Libraries

see [requirements.txt](requirements.txt)

## Issues, Ideas And Bugs

If you have further ideas or you found some bugs, great! Create an [issue](https://github.com/achim0x/tbd/issues) or if you are able and willing to fix it by yourself, clone the repository and create a pull request.

## License

The whole source code is published under [BSD-3-Clause](https://github.com/achim0x/template/blob/main/LICENSE).
Consider the different licenses of the used third party libraries too!

## Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in the work by you, shall be licensed as above, without any additional terms or conditions.
