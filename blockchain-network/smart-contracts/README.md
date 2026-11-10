# Smart Contracts - Deployment Guide

Solidity smart contracts implementing the RODEO decentralized organization for autonomous robot coordination.

## Overview

This directory contains the smart contracts that power the RODEO system. The contracts handle task registration, service coordination, escrow management, and token economics for autonomous robot fleets.

📖 **For detailed contract architecture and functionality, see [contracts/README.md](contracts/README.md)**

---

## Deployment Options

You can deploy the smart contracts using one of two methods:

### Option 1: Docker Deployment (Recommended)

**No installation required on your host machine!**

Deploy using Docker containers. This method doesn't require installing Node.js, npm, or Hardhat on your system.

```bash
# Start Ganache (if not already running)
cd blockchain-network/ganache-docker
docker compose up -d

# Deploy contracts
cd ../smart-contracts/docker
./deploy.sh
```
**Expected output**:
```
✅ Contracts deployed successfully:
IECoin:          0x851356ae760d987E095750cCeb3bC6014560891C
Organization:    0x72F375F23BCDA00078Ac12e7e9E7f6a8CA523e7D
ServiceManager:  0xf23B8c9debCdCEa2a40E81c3f6d786987069D40d
TaskManager:     0x376698f160E16978f2Cc0339ff72887923E5F3a1
📝 Saved deployment to /app/deployments/1337.json

💰 Distributing IEC tokens...
```
The deployment addresses are automatically saved to blockchain-network/smart-contracts/deployments/1337.json

📖 **See [docker/README.md](docker/README.md) for detailed Docker deployment instructions**

### Option 2: Local Deployment (Native)

Deploy directly from your host machine. Requires Node.js and npm installed.

#### Prerequisites

```bash
# Check if Node.js is installed
node --version  # Should be v18 or higher
npm --version
```

If not installed, see [Node.js installation guide](https://nodejs.org/)

#### Steps

1. **Install dependencies:**
```bash
cd blockchain-network/smart-contracts
npm install
```

2. **Configure environment:**

Create a `.env` file with the following:
```env
GANACHE_URL=http://127.0.0.1:8545
PRIVATE_KEY_DEPLOYER=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
PRIVATE_KEY_ORGANIZATION=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
PRIVATE_KEY_ORACLE=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
PRIVATE_KEY_HUMAN=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
PRIVATE_KEY_ROBOT=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a
```

3. **Compile and deploy contracts:**
```bash
cd blockchain-network/smart-contracts
npm install
npx hardhat compile
npx hardhat run scripts/deploy.js --network localhost
```
**Expected output**:
```
✅ Contracts deployed successfully:
IECoin:          0x851356ae760d987E095750cCeb3bC6014560891C
Organization:    0x72F375F23BCDA00078Ac12e7e9E7f6a8CA523e7D
ServiceManager:  0xf23B8c9debCdCEa2a40E81c3f6d786987069D40d
TaskManager:     0x376698f160E16978f2Cc0339ff72887923E5F3a1
📝 Saved deployment to /app/deployments/1337.json

💰 Distributing IEC tokens...

---

## After Deployment

### Generated Artifacts

After successful deployment, you'll find:

#### 1. Contract ABIs
**Location:** `artifacts/contracts/[ContractName].sol/[ContractName].json`

Each contract has a JSON file containing:
- `abi` - Application Binary Interface (for interacting with the contract)
- `bytecode` - Compiled contract code
- `deployedBytecode` - Deployed version of bytecode
- `metadata` - Compilation metadata

**Example:**
```bash
artifacts/contracts/
├── IECoin.sol/
│   └── IECoin.json
├── Organization.sol/
│   └── Organization.json
├── ServiceManager.sol/
│   └── ServiceManager.json
└── TaskManager.sol/
    └── TaskManager.json
```

#### 2. Deployment Addresses
**Location:** `deployments/1337.json`

Contains deployed contract addresses:
```json
{
  "chainId": 1337,
  "network": "ganache",
  "timestamp": "2026-03-04T10:30:00.000Z",
  "contracts": {
    "IECoin": { "address": "0x1613beB3B2C4f22Ee086B2b38C1476A3cE7f78E8" },
    "Organization": { "address": "0x1C674bf0d074Dc54bb13D1e6291C0cE88054C5b5" },
    "ServiceManager": { "address": "0x12aEdb6639C160B051be89B77717F46eafac282b" },
    "TaskManager": { "address": "0x49A1cc3dDE359E254c48808E4bD83e331A3cC311" }
  }
}
```

---

## Updating Other Components After Deployment

### ⚠️ Important: ABI and Address Updates

**When you modify smart contracts or deploy new once**, you MUST update the following components:

### 1. Update Oracle

The Oracle needs contract addresses and ABIs:

**Update addresses:**
```bash
cd oracle/docker
nano .env
```
Update these variables with your deployed addresses:
```json
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...
```

**Update ABIs:**
The oracle reads the ABIs from the ROS 2 bridge's `abi/` folder
(`BASE_ABI`, mounted by `oracle/docker/docker-compose.yml`; default in
`oracle/oracle_node/settings.py`), so updating the bridge's copies (below)
updates the oracle too. If you define new functions, make sure to edit the
Oracle source code to use those functions.

### 2. Update ROS-ETH Bridge

The ROS 2 bridge keeps the contract ABIs in one folder, used both for colcon
builds and for the Docker image:

```bash
# from blockchain-network/smart-contracts, after `npm run compile`
ABI=../../dao-bridge/ros2-eth-bridge/ros2_ws/src/ros_eth_bridge/abi
for c in TaskManager Organization ServiceManager IECoin; do
  cp artifacts/contracts/$c.sol/$c.json $ABI/
done
```

Then rebuild the bridge image (`docker compose up -d --build` in
`dao-bridge/ros2-eth-bridge/docker`). If you add or change functions, update
the bridge's `eth/dao/` layer to use them.

**Update addresses in bridge configuration:**
```bash
cd dao-bridge/ros2-eth-bridge/docker/configs
nano dao.yaml
```

### 3. Update Web Interface

The web frontend needs contract ABIs and addresses:

```bash
# Copy ABIs
cp artifacts/contracts/*.json dao-bridge/org-web/web/backend/contracts/

# Update addresses in configuration
cd dao-bridge/org-web
nano .env
```
Update these variables:
```bash
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...
```

---

## Testing

Run the test suite to verify contract functionality:

```bash
# Run all tests
npx hardhat test

# Run specific test file
npx hardhat test test/Organization.test.js

# Generate coverage report
npx hardhat coverage
```

📖 **See [test/README.md](test/README.md) for comprehensive testing documentation**
---

## Directory Structure

```
smart-contracts/
├── contracts/             # Solidity smart contracts
│   ├── IECoin.sol         # ERC20 token
│   ├── Organization.sol   # Main coordinator
│   ├── ServiceManager.sol # Service registry
│   ├── TaskManager.sol    # Task lifecycle manager
│   └── README.md          # Contract documentation
├── scripts/               # Deployment scripts
│   └── deploy.js          # Main deployment script
├── test/                  # Contract tests
├── docker/                # Docker deployment setup
│   └── README.md          # Docker documentation
├── artifacts/             # (Generated) Compiled contracts & ABIs
├── deployments/           # (Generated) Deployment addresses
├── cache/                 # (Generated) Hardhat cache
├── hardhat.config.js      # Hardhat configuration
├── package.json           # Node.js dependencies
└── .env                   # Environment configuration
```

---

## License

MIT License - See [LICENSE](../../LICENSE.md)
