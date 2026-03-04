# Quick Start: Deploy Smart Contracts with Docker

Deploy your smart contracts to Ganache without installing Node.js on your host machine.

## Prerequisites

- Docker and Docker Compose installed
- Ganache running in Docker

## Step 1: Start Ganache (if not already running)

```bash
cd blockchain-network/ganache-docker
docker-compose up -d
```

Wait a few seconds for Ganache to initialize.

## Step 2: Verify Configuration

Check that your `.env` file exists in `blockchain-network/smart-contracts/`:

```bash
cat blockchain-network/smart-contracts/.env
```

It should contain:
```env
GANACHE_URL=http://ganache:8545
PRIVATE_KEY_DEPLOYER=0x...
PRIVATE_KEY_ORGANIZATION=0x...
PRIVATE_KEY_ORACLE=0x...
```

## Step 3: Deploy Contracts

```bash
cd blockchain-network/smart-contracts/docker
./deploy.sh
```

The script will:
- ✅ Check if Ganache is running
- 🏗️ Build the Docker image (only if needed)
- 🔨 Compile the smart contracts
- 🚀 Deploy to Ganache
- 💾 Save artifacts and deployment addresses

**Note:** The script only rebuilds the Docker image if it doesn't exist. To force a rebuild (e.g., after changing dependencies in package.json):

```bash
./deploy.sh --rebuild
```

## Step 4: Verify Deployment

Check the deployment was successful:

```bash
# View deployed contract addresses
cat blockchain-network/smart-contracts/deployments/1337.json

# List generated artifacts
ls blockchain-network/smart-contracts/artifacts/contracts/
```

You should see:
- `IECoin.sol/`
- `Organization.sol/`
- `ServiceManager.sol/`
- `TaskManager.sol/`

## What Gets Generated

After deployment, these directories contain:

### `artifacts/`
Complete contract artifacts including:
- ABI (Application Binary Interface)
- Bytecode
- Metadata

### `deployments/`
Deployment information including:
- Contract addresses
- Chain ID
- Deployment timestamp

### `cache/`
Hardhat compilation cache (speeds up subsequent builds)

## Redeploy

To deploy again (e.g., after modifying contracts):

```bash
cd blockchain-network/smart-contracts/docker
./deploy.sh
```

The deployment will automatically recompile your changes. The Docker image doesn't need rebuilding unless you changed package.json dependencies.

**Force rebuild after dependency changes:**

```bash
./deploy.sh --rebuild
```

## Troubleshooting

### "Ganache container is not running"

Start Ganache first:
```bash
cd blockchain-network/ganache-docker
docker-compose up -d
```

### "Connection refused to Ganache"

Check Ganache is accessible:
```bash
docker ps | grep ganache
curl http://localhost:8545
```

### Run Setup Tests

Test your configuration before deploying:
```bash
cd blockchain-network/smart-contracts/docker
./test-setup.sh
```

## Next Steps

After deployment, use the generated artifacts in your applications:

1. **Python/Oracle**: Load ABIs from `artifacts/contracts/[Contract].sol/[Contract].json`
2. **Web/Frontend**: Import contract addresses from `deployments/1337.json`
3. **ROS Bridge**: Configure with deployed contract addresses

## Custom Deployment

To run custom scripts or commands:

```bash
# Interactive shell
docker-compose run --rm smart-contract-deployer sh

# Custom script
docker-compose run --rm smart-contract-deployer npx hardhat run scripts/your-script.js --network ganache

# Only compile (no deploy)
docker-compose run --rm smart-contract-deployer npm run compile
```

---

For more details, see [README.md](README.md)
