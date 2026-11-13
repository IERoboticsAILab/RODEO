# Organization Web Console

Web-based management interface for RODEO blockchain operations. Provides real-time task and service management through a unified dashboard.

## Architecture

**Backend (FastAPI):** REST API for blockchain interactions via Web3.py  
**Frontend (Next.js):** Responsive UI with Mantine components and Tailwind CSS  
**Deployment:** Single Docker container with nginx reverse proxy

## Features

### Task Management
- Order a task from the services that are online: pick a service, fill in its
  parameters (places are dropdowns), add a note
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
docker logs -f org-web-console     # by container name, from anywhere

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
# from the repo root (the image includes robot-agent's rodeo_common)
docker build -f dao-bridge/org-web/Dockerfile -t org-web-console:latest .
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

## The task form

Every task has the same base, whatever the service: **Name**, **Description**,
**Category**, **Type** and **Price**. Category and Type are dropdowns of what the
online services offer, empty at first; choosing a type pre-fills the price and
opens a **details** section with only the fields that service declares, such as
a delivery's pick-up and drop-off places. Fixed services, like a lab tour, have
no details.

## Wallets (MetaMask)

Anyone can post tasks from their own wallet. **Connect MetaMask** (top right)
uses MetaMask Connect EVM (`@metamask/connect-evm`, the successor of the
deprecated `@metamask/sdk`) and shows the connected address and its IEC
balance.

1. **Connect MetaMask**, approve in MetaMask. (To show MetaMask's icon on the
   button, add their official `metamask.svg` to `web/public/`.)
2. **Switch to RODEO local** if MetaMask is on another network; the console
   adds the network to MetaMask if needed (chain 1337, RPC `WALLET_RPC_URL`).
3. On the local chain, **Get test funds** sends a new wallet some ETH (for gas)
   and IEC from the organization's wallet (`/faucet`, once per address per 10
   minutes; off on other chains).
4. Post a task as usual. MetaMask asks twice: to let the TaskManager take the
   reward into escrow, then to post the task. The backend still checks the task
   (`/tasks/prepare`) and writes its description; the wallet signs and pays, so
   it is the task's creator and receives the refund if the task is rejected.

With a wallet connected, **My tasks** lists that wallet's tasks, and Remove /
Activate are signed by it (the contract allows only a task's creator).

## Admin: the organization's wallet

The console holds the organization's key, so using it is admin-only. Without
an admin PIN the console is wallet-only: people post with MetaMask, and every
request that would sign with the organization's key is refused.

To allow an admin: copy `.env.admin.example` to `.env.admin` (not committed),
set `ORG_ADMIN_PIN`, and restart org-web. Then **Unlock** with the PIN on the
Home page (Organization (admin)); it lasts for that browser tab. Unlocked:

- the task form offers **Pay from: my wallet / the organization**;
- the organization's task funds and deposit box appear on the Home page;
- the Services page can register and manage the organization's services, and
  the Tasks page lists the organization's tasks with their actions.

The backend enforces it: the ten endpoints that sign with the organization's key
require the PIN in the `X-Admin-Pin` header (a wrong PIN is answered after a
second's delay). Reading, `/tasks/prepare` and the local-chain faucet stay open.
Over the lab network, serve the console over HTTPS so the PIN isn't sent in the
clear.

Settings: `WALLET_RPC_URL` is the RPC URL as seen from the **browser**
(`http://localhost:8545` on the PC; the server's address when org-web runs on
medusa), `WALLET_CHAIN_NAME`, `DEV_FAUCET` (empty = on for chain 1337 only),
`FAUCET_ETH`, `FAUCET_IEC`, `FAUCET_COOLDOWN_SEC`.

Contract behaviour to know: removing a task does **not** refund its reward, and
reactivating it takes the reward again; the console warns before removing.

### Organization task funds

Tasks posted from the console are paid by the Organization contract from its
deposit, shown as **Organization task funds** on the Home page with a deposit box
(`GET /organization/balance`, `POST /organization/deposit`). The deposit first
approves the Organization contract, then deposits. A task is refused with a
clear message when the funds don't cover its price.

Contract behaviour to know: `Organization.deposit` *sets* the TaskManager's
allowance to the amount deposited rather than adding to it, so the funds
available after a deposit equal that deposit. Unspent funds from earlier
deposits, and refunds from rejected tasks, stay in the contract but can't be
used. Deposit when the funds run low.

The Tasks page is built from `GET /catalog`, which lists one entry per kind of
service (category and task type) that an **active** service offers:

- offline (inactive) services do not appear;
- if every provider of a kind is busy, it is listed as "will queue": the task
  waits on chain until one is free;
- the parameters and places come from the on-chain description of the service
  the contract would pick (the cheapest free one), so the form always matches
  the robot that will do the task. Defaults are pre-filled;
- services marked `robot_only` (charging) are left out: robots order those;
- the reward is pre-filled with the price that gets the task picked up now. A
  robot is paid its service price; anything above it stays in the contract.

The backend checks the parameters against the same schema (with
`rodeo_common`, shared with the robot agents and the oracle) and writes the
task description as `{"v":1,"title":"...","params":{...},"note":"..."}`; the
contract has no field for a title, so it lives in the description. A request
without `params` is posted as free text, as before.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contracts` | Contract addresses |
| GET | `/catalog` | Kinds of service that can be ordered now, with schema and places |
| GET | `/admin/status` | Whether an admin PIN is configured |
| POST | `/admin/check` | 200 if the `X-Admin-Pin` header is right |
| GET | `/wallet/config` | Chain, wallet RPC URL, contract addresses, faucet on/off |
| POST | `/tasks/prepare` | Check a task and return it for the user's wallet to sign and pay |
| POST | `/faucet` | Local chain only: test ETH and IEC for a wallet |
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

From a source checkout, `rodeo_common` is found in `robot-agent/` automatically.
Tests: `python -m pytest tests`.

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
