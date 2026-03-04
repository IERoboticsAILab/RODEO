# Configuration Update Summary

## Contract Address Update Location

**Primary File:** `configs/dao.yaml`

**What to Update:**

```yaml
contracts:
  iecoin: "0x..."              # ⬅️ Your IECoin contract address
  organization: "0x..."         # ⬅️ Your Organization contract address
  task_manager: "0x..."         # ⬅️ Your TaskManager contract address
  service_manager: "0x..."      # ⬅️ Your ServiceManager contract address

wallet:
  address: "0x..."              # ⬅️ Your wallet address (from wallet.json)
```

## Where to Find Contract Addresses

### Option 1: From Deployment Artifacts

```bash
cat ../../blockchain-network/smart-contracts/deployments/1337.json
```

### Option 2: From Deployment Logs

When you run the deployment script, addresses are printed:

```
✅ IECoin deployed to: 0x...
✅ Organization deployed to: 0x...
✅ TaskManager deployed to: 0x...
✅ ServiceManager deployed to: 0x...
```

### Option 3: From org-web addresses.json

If org-web is already configured:

```bash
cat /home/lab/repos/robotic_decentralized_organization/dao-bridge/org-web/backend/addresses.json
```

## Wallet Address

Get your wallet address from the keystore file:

```bash
cat ~/.ros_eth/wallet.json | jq -r '.address'
```

## RPC Endpoints

If blockchain is on a different host, update:

```yaml
chain:
  rpc_url: ws://YOUR_IP:8545
  http_fallback_url: http://YOUR_IP:8545
```

## Quick Update CLI

```bash
cd /home/lab/repos/robotic_decentralized_organization/dao-bridge/ros-eth-bridge/docker

# Edit configuration
nano configs/dao.yaml

# Check configuration is valid
./ros-eth-bridge-docker.sh check

# Restart bridge (no rebuild needed)
./ros-eth-bridge-docker.sh restart
```

## Files Created for Docker Setup

1. **docker-compose.yml** - Orchestration file
2. **.env.example** - Environment variable template
3. **configs/dao.yaml.template** - Configuration template
4. **ros-eth-bridge-docker.sh** - Helper script (executable)
5. **README.md** - Comprehensive documentation
6. **QUICKSTART.md** - Quick start guide
7. **CONFIG-UPDATE.md** - This file
8. **.gitignore** - Git ignore patterns

## No Changes Needed

These are **already correct** and mounted from host:

- ABI files (in `catkin_ws/src/ros_eth_bridge/abi/`)
- Wallet keystore (at `~/.ros_eth/wallet.json`)

## After Updating

1. Save `dao.yaml`
2. Restart: `./ros-eth-bridge-docker.sh restart`
3. Check logs: `./ros-eth-bridge-docker.sh logs`
4. Verify nodes: `./ros-eth-bridge-docker.sh rosnode`

## Validation

Ensure addresses match across all components:

```bash
# Bridge config
grep -A4 "^contracts:" configs/dao.yaml

# org-web config (should match)
cat ../org-web/backend/addresses.json | jq '.contracts'

# Oracle config (should match)
cat ../../oracle/addresses.json | jq '.contracts'
```

All should have **identical contract addresses**!
