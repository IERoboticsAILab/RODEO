# Docker Deployment for Smart Contracts

Deploy smart contracts to Ganache using Docker - no Node.js installation required on your host!

## Overview

This Docker setup compiles and deploys the smart contracts from the `smart-contracts/` folder to your Ganache blockchain. All artifacts (ABIs, deployment addresses) are saved back to the `smart-contracts/` folder for use by other components.

**What gets deployed:** All contracts in `../contracts/`
- `IECoin.sol` - ERC20 token
- `Organization.sol` - Main coordinator
- `ServiceManager.sol` - Service registry  
- `TaskManager.sol` - Task lifecycle manager

**Where artifacts are saved:**
- `../artifacts/` - Compiled contracts and ABIs
- `../deployments/` - Contract addresses and deployment info
- `../cache/` - Hardhat compilation cache

---

## Prerequisites

- Docker and Docker Compose installed
- Ganache running (via Docker or on host)
- `.env` file configured in `smart-contracts/` directory

## Quick Start

### 1. Start Ganache

```bash
cd blockchain-network/ganache-docker
docker compose up -d
```

Wait a few seconds for Ganache to initialize.

### 2. Deploy Contracts

```bash
cd blockchain-network/smart-contracts/docker
./deploy.sh
```

That's it! The script will:
- ✅ Check Ganache connectivity
- ✅ Build Docker image (first time only)
- ✅ Compile all contracts
- ✅ Deploy to Ganache
- ✅ Save artifacts to `smart-contracts/artifacts/`
- ✅ Save addresses to `smart-contracts/deployments/1337.json`

---

## Expected Output

### Successful Deployment

```bash
═══════════════════════════════════════════════════════
  Smart Contract Deployment (Docker)
═══════════════════════════════════════════════════════

🔍 Checking if Ganache is running...
🔗 Testing connection to Ganache...
   ✅ Ganache is accessible

📦 Using existing image (use --rebuild to force rebuild)

🚀 Deploying smart contracts...

Compiled 15 Solidity files successfully

✅ Contracts deployed successfully:

IECoin:          0x1613beB3B2C4f22Ee086B2b38C1476A3cE7f78E8
Organization:    0x1C674bf0d074Dc54bb13D1e6291C0cE88054C5b5
ServiceManager:  0x12aEdb6639C160B051be89B77717F46eafac282b
TaskManager:     0x49A1cc3dDE359E254c48808E4bD83e331A3cC311

📝 Saved deployment to /app/deployments/1337.json

💰 Distributing IEC tokens...

✅ Transferred 2000 IEC to Human (0x70...a6)
   Balance: 2000.0 IEC
✅ Transferred 2000 IEC to Organization (0x59...0d)
   Balance: 2000.0 IEC
✅ Transferred 2000 IEC to Robot (0x47...6a)
   Balance: 2000.0 IEC

✅ Token distribution complete!

═══════════════════════════════════════════════════════
✅ Deployment complete!

📁 Artifacts saved to: /path/to/smart-contracts/artifacts
📝 Deployment info:    /path/to/smart-contracts/deployments
═══════════════════════════════════════════════════════
```

---

## Configuration

### Environment Variables

The `.env` file in `smart-contracts/` must contain:

```env
GANACHE_URL=http://host.docker.internal:8545
PRIVATE_KEY_DEPLOYER=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
PRIVATE_KEY_ORGANIZATION=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
PRIVATE_KEY_ORACLE=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
PRIVATE_KEY_HUMAN=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
PRIVATE_KEY_ROBOT=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a
```

**Important:** Use `host.docker.internal:8545` for the URL when deploying from Docker.

### Volume Mounts

These directories are mounted from host to container:

```yaml
volumes:
  - ../artifacts:/app/artifacts      # Contract ABIs (output)
  - ../deployments:/app/deployments  # Contract addresses (output)
  - ../cache:/app/cache              # Compilation cache (output)
  - ../.env:/app/.env:ro             # Configuration (read-only)
```

---

## See Also

- [Smart Contracts README](../README.md) - Deployment options overview
- [Contracts Documentation](../contracts/README.md) - Contract architecture
- [Quick Start Guide](QUICKSTART.md) - Step-by-step deployment guide

---

## License

MIT License
