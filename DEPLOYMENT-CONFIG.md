# RODEO Smart Contract Configuration Guide

After deploying new smart contracts, you need to update the addresses in multiple components. This guide shows where to update them.

## 1. Finding Your Deployed Addresses

After running the Hardhat deployment:

```bash
cd blockchain-network/smart-contracts
cat deployments/1337.json
```

This file contains all deployed contract addresses for chain ID 1337 (local Ganache).

## 2. Update Oracle Configuration

**Location**: `oracle/docker/.env`

```bash
cd oracle/docker
nano .env
```

Update these values:
```bash
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...

ORACLE_ADDRESS=0x...
ORACLE_PRIVATE_KEY=0x...
```

Restart:
```bash
docker compose restart
# or
./oracle-docker.sh restart
```

**📖 Detailed guide**: [oracle/docker/CONFIG-UPDATE.md](oracle/docker/CONFIG-UPDATE.md)

## 3. Update Org-Web Configuration

**Location**: `dao-bridge/org-web/.env`

```bash
cd dao-bridge/org-web
nano .env
```

Update these values:
```bash
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...

# Organization wallet
ORGANIZATION_ADDRESS_WALLET=0x...
ORGANIZATION_PRIVATE_KEY=0x...
```

Restart:
```bash
docker compose restart
```

**📖 Detailed guide**: `dao-bridge/org-web/.env` (has inline comments)

## 4. Update ROS-Ethereum Bridge Configuration

**Location**: `dao-bridge/ros-eth-bridge/docker/configs/dao.yaml`

```bash
cd dao-bridge/ros-eth-bridge/docker/configs
nano dao.yaml
```

Update the `contracts` section:
```yaml
contracts:
  Organization: "0x..."
  TaskManager: "0x..."
  ServiceManager: "0x..."
  IECoin: "0x..."
```

Update wallet info if needed:
```yaml
wallet:
  address: "0x..."
  keystore: "/root/.ros_eth_wallet/wallet.json"
```

Restart:
```bash
cd ..
docker compose restart
```

**📖 Detailed guide**: [dao-bridge/ros-eth-bridge/docker/CONFIG-UPDATE.md](dao-bridge/ros-eth-bridge/docker/CONFIG-UPDATE.md)

## 5. Update Robot Demo Scripts (Optional)

If you have robot scripts that directly interact with contracts:

**Locations**:
- `quick-start/robot_emulator_demo.py`
- `quick-start/demo.py`
- Custom robot scripts

These typically don't hardcode addresses, instead they:
- Use ROS parameters (loaded from dao.yaml)
- Call ROS action servers (which use the bridge configuration)

**No update needed** as long as the ROS-Ethereum bridge is configured correctly.

## Quick Update Script

For convenience, here's a one-liner to update all three components after deployment:

```bash
# Get the new addresses
NEW_ORG=$(jq -r '.contracts.Organization' blockchain-network/smart-contracts/deployments/1337.json)
NEW_TM=$(jq -r '.contracts.TaskManager' blockchain-network/smart-contracts/deployments/1337.json)
NEW_SM=$(jq -r '.contracts.ServiceManager' blockchain-network/smart-contracts/deployments/1337.json)
NEW_IEC=$(jq -r '.contracts.IECoin' blockchain-network/smart-contracts/deployments/1337.json)

# Update oracle .env
sed -i "s/ORGANIZATION_ADDRESS=.*/ORGANIZATION_ADDRESS=$NEW_ORG/" oracle/docker/.env
sed -i "s/TASK_MANAGER_ADDRESS=.*/TASK_MANAGER_ADDRESS=$NEW_TM/" oracle/docker/.env
sed -i "s/SERVICE_MANAGER_ADDRESS=.*/SERVICE_MANAGER_ADDRESS=$NEW_SM/" oracle/docker/.env
sed -i "s/IECOIN_ADDRESS=.*/IECOIN_ADDRESS=$NEW_IEC/" oracle/docker/.env

# Update org-web .env
sed -i "s/ORGANIZATION_ADDRESS=.*/ORGANIZATION_ADDRESS=$NEW_ORG/" dao-bridge/org-web/.env
sed -i "s/TASK_MANAGER_ADDRESS=.*/TASK_MANAGER_ADDRESS=$NEW_TM/" dao-bridge/org-web/.env
sed -i "s/SERVICE_MANAGER_ADDRESS=.*/SERVICE_MANAGER_ADDRESS=$NEW_SM/" dao-bridge/org-web/.env
sed -i "s/IECOIN_ADDRESS=.*/IECOIN_ADDRESS=$NEW_IEC/" dao-bridge/org-web/.env

# Update ros-eth-bridge dao.yaml
sed -i "s/Organization: .*/Organization: \"$NEW_ORG\"/" dao-bridge/ros-eth-bridge/docker/configs/dao.yaml
sed -i "s/TaskManager: .*/TaskManager: \"$NEW_TM\"/" dao-bridge/ros-eth-bridge/docker/configs/dao.yaml
sed -i "s/ServiceManager: .*/ServiceManager: \"$NEW_SM\"/" dao-bridge/ros-eth-bridge/docker/configs/dao.yaml
sed -i "s/IECoin: .*/IECoin: \"$NEW_IEC\"/" dao-bridge/ros-eth-bridge/docker/configs/dao.yaml

echo "✅ All configurations updated!"
echo "Now restart the Docker containers:"
echo "  cd oracle/docker && docker compose restart"
echo "  cd dao-bridge/org-web && docker compose restart"
echo "  cd dao-bridge/ros-eth-bridge/docker && docker compose restart"
```

## Configuration Priority

Each component follows this priority order:

### Oracle
1. Environment variables (`.env` file) ⭐ **RECOMMENDED**
2. `addresses.json` file (fallback)

### Org-Web
1. Environment variables (`.env` file) ⭐ **RECOMMENDED**
2. `backend/addresses.json` file (fallback)

### ROS-Ethereum Bridge
1. `configs/dao.yaml` file ⭐ **ONLY OPTION**

## Verification

After updating, verify each component:

### Oracle
```bash
docker logs rodeo-oracle --tail 20
# Look for: "✅ Oracle configuration loaded from environment variables"
```

### Org-Web
```bash
docker logs rodeo-org-web --tail 20
# Look for: "✅ Configuration loaded via environment variables"
```

### ROS-Ethereum Bridge
```bash
docker logs ros-eth-bridge --tail 50
# Look for: "dao_listener ready — chain 1337"
# Look for: "dao_writer ready — chain 1337"
```

## Troubleshooting

**Problem**: Services start but can't interact with contracts

**Solution**: Verify addresses match deployment:
```bash
# Check what each service is using
docker logs rodeo-oracle | grep -i address
docker logs rodeo-org-web | grep -i address
docker logs ros-eth-bridge | grep -i chain

# Compare with deployment
cat blockchain-network/smart-contracts/deployments/1337.json
```

**Problem**: "Contract not deployed" errors

**Solution**: Ensure blockchain is running and contracts are deployed at the specified addresses

**Problem**: Transaction failures

**Solution**: Check that wallet addresses have sufficient ETH balance
