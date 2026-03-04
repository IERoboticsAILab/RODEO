# Organization Web Console

Web-based management interface for RODEO blockchain operations. Provides real-time task and service management through a unified dashboard.

## Architecture

**Backend (FastAPI):** REST API for blockchain interactions via Web3.py  
**Frontend (Next.js):** Responsive UI with Mantine components and Tailwind CSS  
**Deployment:** Single Docker container with nginx reverse proxy

## Features

### Task Management
- Register new tasks with reward allocation
- Activate/deactivate tasks
- Monitor task assignment and execution
- Submit proof of completion
- View organization balance and deposit funds

### Service Management
- Register robot services with pricing
- Control service availability
- Track service utilization

### Token Operations
- View IECoin holder balances
- Monitor transaction history
- Fund organization contract

## Quick Start with Docker Compose

### Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- Running blockchain (Ganache or other)
- Deployed smart contracts (Organization, IECoin, TaskManager, ServiceManager)

### 1. Configure Environment

Copy the example environment file and edit with your values:

```bash
cd /home/lab/repos/robotic_decentralized_organization/dao-bridge/org-web
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Blockchain
RPC_URL=http://10.205.10.9:8545

# Contract Addresses (from deployment)
ORGANIZATION_ADDRESS=0xcEC91d876E8f003110D43381359b1bAd124e7F2b
IECOIN_ADDRESS=0x0B306BF915C4d645ff596e518fAf3F9669b97016

# Organization Wallet (from addresses.json)
ORGANIZATION_WALLET_PUBLIC=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
ORGANIZATION_WALLET_PRIVATE=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d

# Application
HOST_PORT=8080
NEXT_PUBLIC_API_BASE=http://localhost:8080
```

**Important:** Get these values from:
- Contract addresses: `blockchain-network/smart-contracts/deployments/1337.json`
- Wallet credentials: Your addresses configuration file
- RPC_URL: Your blockchain endpoint

### 2. Build and Start

```bash
docker-compose up -d --build
```

Or use individual commands:

```bash
# Build the image
docker-compose build

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 3. Access the Console

Open your browser to:
```
http://localhost:8080
```

## Configuration Options

The application can be configured via:

1. **Environment variables** (Recommended for Docker)
2. **addresses.json file** (Fallback)

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `RPC_URL` | Blockchain RPC endpoint | Yes | `http://localhost:8545` |
| `ORGANIZATION_ADDRESS` | Organization contract | Yes | - |
| `IECOIN_ADDRESS` | IECoin token contract | Yes | - |
| `ORGANIZATION_WALLET_PUBLIC` | Org wallet address | Yes | - |
| `ORGANIZATION_WALLET_PRIVATE` | Org wallet private key | Yes | - |
| `HOST_PORT` | Port to expose console | No | `8080` |
| `NEXT_PUBLIC_API_BASE` | Frontend API URL | No | `http://localhost:8080` |
| `ABI_ROOT` | ABI files directory | No | `contracts` |
| `ADDRESSES_JSON` | Config file path | No | `addresses.json` |
| `CORS_ORIGINS` | Allowed CORS origins | No | (empty) |

### File-Based Configuration

If not using environment variables, create `backend/addresses.json`:

```json
{
  "rpc_url": "http://10.205.10.9:8545",
  "abi_root": "contracts",
  "contracts": {
    "Organization": "0xcEC91d876E8f003110D43381359b1bAd124e7F2b",
    "IECoin": "0x0B306BF915C4d645ff596e518fAf3F9669b97016"
  },
  "wallets": {
    "organization": {
      "public": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
      "private": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    }
  }
}
```

**Note:** Environment variables take precedence over the JSON file.

## Manual Docker Commands

### Build

```bash
docker build -t org-web-console:latest .
```

### Run with Environment Variables

```bash
docker run -d \
  --name org-web-console \
  -p 8080:80 \
  -e RPC_URL=http://10.205.10.9:8545 \
  -e ORGANIZATION_ADDRESS=0xcEC91d876E8f003110D43381359b1bAd124e7F2b \
  -e IECOIN_ADDRESS=0x0B306BF915C4d645ff596e518fAf3F9669b97016 \
  -e ORGANIZATION_WALLET_PUBLIC=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
  -e ORGANIZATION_WALLET_PRIVATE=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
  org-web-console:latest
```

### Run with .env File

```bash
docker run -d \
  --name org-web-console \
  -p 8080:80 \
  --env-file .env \
  org-web-console:latest
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contracts` | Contract addresses |
| GET | `/tasks` | List all tasks |
| POST | `/tasks/register` | Create new task |
| POST | `/tasks/activate` | Enable task assignment |
| POST | `/tasks/submit-proof` | Submit execution proof |
| GET | `/services` | List all services |
| POST | `/services/register` | Register new service |
| POST | `/services/set-busy` | Update availability |
| GET | `/balances` | Get IEC token balances |
| GET | `/organization/balance` | Get organization contract balance |
| POST | `/organization/deposit` | Deposit IEC to organization |

Full API documentation available at `http://localhost:8080/docs` when running.

## Development

For local development without Docker:

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables or create addresses.json
export RPC_URL=http://10.205.10.9:8545
export ORGANIZATION_ADDRESS=0x...
# ... other vars

uvicorn main:app --reload --port 8000
```

Backend runs on `http://localhost:8000`

### Frontend

```bash
cd web
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

## Support

For issues or questions:
- Check container logs: `docker-compose logs -f`
- Verify configuration: `docker exec org-web-console env | grep -E "RPC_URL|ORGANIZATION|IECOIN"`
- Test blockchain connection: `docker exec org-web-console curl -X POST $RPC_URL ...`
- Review FastAPI docs: `http://localhost:8080/docs`
