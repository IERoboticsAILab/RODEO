# Blockchain Network

The blockchain layer of RODEO, containing smart contracts for decentralized robot coordination and local blockchain infrastructure for development/testing.

## Contents
- **[smart-contracts/](smart-contracts/)**: Solidity contracts, tests, and deployment scripts
- **[ganache-docker/](ganache-docker/)**: Local Ethereum blockchain (Ganache) for testing

## Purpose
This layer provides:
- ✅ Task marketplace with escrow mechanism
- ✅ Service registry and matching
- ✅ Token economy (IECoin - ERC20)
- ✅ Oracle-based task verification

## Architecture Overview

The blockchain network consists of 4 main smart contracts:

- **Organization.sol** - Main coordinator (entry point)
- **TaskManager.sol** - Task lifecycle & escrow management  
- **ServiceManager.sol** - Service registry & matching
- **IECoin.sol** - ERC20 token for payments

📖 **See [smart-contracts/README.md](smart-contracts/README.md) for detailed contract documentation, API reference, and gas costs.**

---

## Quick Start

### Prerequisites
- **Docker & Docker Compose** (for Ganache and smart contract deployment)

### Deployment

#### Step 1: Start Local Blockchain
```bash
cd blockchain-network/ganache-docker
docker compose up -d

# Verify it's running
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Expected output: {"jsonrpc":"2.0","id":1,"result":"0x0"}
```

**What's running?**
- Ganache local Ethereum blockchain on port 8545
- 20 pre-funded test accounts
- Chain ID: 1337
- Persisted data in `ganache_db/` volume

#### Step 2: Deploy Smart Contracts (Docker)
```bash
cd ../smart-contracts/docker
./deploy.sh
```

**What happens:**
- ✅ Checks Ganache connectivity
- ✅ Builds Docker image (first time only)
- ✅ Compiles all Solidity contracts
- ✅ Deploys to Ganache
- ✅ Saves ABIs to `smart-contracts/artifacts/`
- ✅ Saves addresses to `smart-contracts/deployments/1337.json`

**Expected output:**
```
═══════════════════════════════════════════════════════
  Smart Contract Deployment (Docker)
═══════════════════════════════════════════════════════

🔍 Checking if Ganache is running...
🔗 Testing connection to Ganache...
   ✅ Ganache is accessible

📦 Using existing image (use --rebuild to force rebuild)

🚀 Deploying smart contracts...

✅ Contracts deployed successfully:

IECoin:          0x1613beB3B2C4f22Ee086B2b38C1476A3cE7f78E8
Organization:    0x1C674bf0d074Dc54bb13D1e6291C0cE88054C5b5
ServiceManager:  0x12aEdb6639C160B051be89B77717F46eafac282b
TaskManager:     0x49A1cc3dDE359E254c48808E4bD83e331A3cC311

📝 Saved deployment to /app/deployments/1337.json

💰 Distributing IEC tokens...
✅ Transferred 2000 IEC to Human
✅ Transferred 2000 IEC to Organization
✅ Transferred 2000 IEC to Robot

═══════════════════════════════════════════════════════
✅ Deployment complete!
═══════════════════════════════════════════════════════
```

✅ **Done!** Your contracts are now deployed and ready for integration with the DAO bridge.

**Quick redeployment:** Just run `./deploy.sh` again. Docker rebuild is only needed if you change `package.json` dependencies.

**Alternative:** For native deployment (requires Node.js), see [smart-contracts/README.md](smart-contracts/README.md#option-2-local-deployment-native)

📖 **For detailed information:**
- Contract operations & API: [smart-contracts/README.md](smart-contracts/README.md)
- Testing documentation: [smart-contracts/test/README.md](smart-contracts/test/README.md)

---

## License
MIT License - See [LICENSE](../LICENSE)
