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

**Location**: `dao-bridge/ros2-eth-bridge/docker/configs/dao.yaml`

```bash
cd dao-bridge/ros2-eth-bridge/docker/configs
nano dao.yaml
```

Update the `contracts` section:
```yaml
contracts:
  iecoin: "0x..."
  organization: "0x..."
  task_manager: "0x..."
  service_manager: "0x..."
```

The wallet section names the robot's address and keystore (created with
`dao-bridge/ros2-eth-bridge/scripts/make_wallet.py`):
```yaml
wallet:
  keystore_path: ~/.ros_eth/wallet.json
  address: "15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
```

Restart:
```bash
cd ..
docker compose restart
```

**📖 Detailed guide**: [dao-bridge/ros2-eth-bridge/README.md](dao-bridge/ros2-eth-bridge/README.md)

## 5. Robot scripts

Robots never hold contract addresses themselves: they call the bridge's actions
and services, and the bridge reads `dao.yaml`. The demo in
`quick-start/` needs no update.

## IE Coin on OP Sepolia

The lab's IE Coin runs on **OP Sepolia** (chain id `11155420`, RPC
`https://sepolia.optimism.io`, explorer https://sepolia-optimism.etherscan.io,
lab explorer https://iecoin.cyphy.life); see IERoboticsAILab/iecoin#1. Its
Organization, ServiceManager and TaskManager are the code from before the
on-chain time limits, so org-web keeps the limits (`task_timer.py`). The local
Ganache settings stay the default; OP Sepolia is chosen per component:

| Component | OP Sepolia settings | Key |
|---|---|---|
| org-web | `dao-bridge/org-web/.env.opsepolia` (from `.env.opsepolia.example`) | operator (Organization owner) `0xdB3E…0146` |
| oracle | `oracle/docker/.env.opsepolia` (from `.env.opsepolia.example`) | oracle `0xE384…Ac4e` |
| bridge | `dao-bridge/ros2-eth-bridge/docker/configs/dao.opsepolia.yaml` | robot `0xf31e…917f`, keystore `~/.ros_eth/wallet_opsepolia.json` |

The keys are in Bitwarden (CyPhy Life → Lab Infra, "RODEO Sepolia wallets +
contracts"). The `.env.opsepolia` files are gitignored; never put these keys in a
tracked file.

Once:

```bash
cd ~/rodeo-ros2
# robot keystore (Enter = empty passphrase); the key is read without echo
read -rs -p "robot private key: " ROBOT_PRIVATE_KEY; echo; export ROBOT_PRIVATE_KEY
python3 dao-bridge/ros2-eth-bridge/scripts/make_wallet.py --out ~/.ros_eth/wallet_opsepolia.json
unset ROBOT_PRIVATE_KEY
cp dao-bridge/org-web/.env.opsepolia.example dao-bridge/org-web/.env.opsepolia   # add the operator key
cp oracle/docker/.env.opsepolia.example oracle/docker/.env.opsepolia             # add the oracle key
```

Start (Ganache not needed):

```bash
cd ~/rodeo-ros2/oracle/docker && docker compose --env-file .env.opsepolia up -d --force-recreate
cd ~/rodeo-ros2/dao-bridge/org-web && docker compose --env-file .env.opsepolia up -d --force-recreate
cd ~/rodeo-ros2/dao-bridge/ros2-eth-bridge/docker
DAO_CONFIG=dao.opsepolia.yaml WALLET_PATH=~/.ros_eth/wallet_opsepolia.json \
ROS_DOMAIN_ID=41 ROBOT_NAMESPACE=panther RMW_IMPLEMENTATION=rmw_cyclonedds_cpp docker compose up -d --force-recreate
cd ~/rodeo-ros2/quick-start/docker
ROS_DOMAIN_ID=41 ROBOT_NAMESPACE=panther RMW_IMPLEMENTATION=rmw_cyclonedds_cpp docker compose up -d --no-deps --force-recreate agent
```

Check: the bridge logs `chain 11155420`; the agent registers its service (first
time on the new contracts); org-web's catalog lists it with the 15 min limit and
the org-web log says `task timer: limits {'Logistics': 900}`. Deposit IEC into the
Organization (org-web, organization box) before posting tasks from it. Back to
Ganache: the same commands without `--env-file`, `DAO_CONFIG` and `WALLET_PATH`.

## Quick Update Script

`scripts/update-addresses.sh` updates the oracle, org-web and bridge configs in
one go (it installs `jq` if missing):

```bash
./scripts/update-addresses.sh blockchain-network/smart-contracts/deployments/1337.json
```

Then restart the containers:

```bash
cd oracle/docker && docker compose restart
cd ../../dao-bridge/org-web && docker compose restart
cd ../ros2-eth-bridge/docker && docker compose restart
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
docker logs org-web-console --tail 20
# Look for: "✅ Configuration loaded via environment variables"
```

### ROS-Ethereum Bridge
```bash
docker logs ros2-eth-bridge --tail 50
# Look for: "dao_listener ready — chain 1337"
# Look for: "dao_writer ready — chain 1337"
```

## Troubleshooting

**Problem**: Services start but can't interact with contracts

**Solution**: Verify addresses match deployment:
```bash
# Check what each service is using
docker logs rodeo-oracle | grep -i address
docker logs org-web-console | grep -i address
docker logs ros2-eth-bridge | grep -i ready

# Compare with deployment
cat blockchain-network/smart-contracts/deployments/1337.json
```

**Problem**: "Contract not deployed" errors

**Solution**: Ensure blockchain is running and contracts are deployed at the specified addresses

**Problem**: Transaction failures

**Solution**: Check that wallet addresses have sufficient ETH balance
