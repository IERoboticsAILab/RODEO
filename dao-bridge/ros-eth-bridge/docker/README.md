# ROS-ETH Bridge Docker

Docker container for the RODEO ROS-Ethereum bridge that connects ROS action servers with blockchain smart contracts.

## Overview

The ROS-ETH Bridge provides:
- **ROS Action Servers** for task and service registration, proof submission
- **Blockchain event listening** and publishing to ROS topics
- **Bidirectional communication** between ROS ecosystem and Ethereum

## Quick Start

### Prerequisites

- Docker and Docker Compose V2
- Running blockchain (Ganache at `ws://localhost:8545`)
- Running ROS Master (`roscore`)
- Deployed smart contracts (Organization, TaskManager, ServiceManager, IECoin)
- Wallet keystore JSON file

### 1. Configure Contract Addresses

Update `configs/dao.yaml` with your deployed contract addresses:

```bash
# Get contract addresses from deployment
cat ../../blockchain-network/smart-contracts/deployments/1337.json

# Edit dao.yaml with your addresses
nano configs/dao.yaml
```

**Key sections to update:**

```yaml
contracts:
  iecoin: "0x..."              # ⚠️ UPDATE
  organization: "0x..."         # ⚠️ UPDATE
  task_manager: "0x..."         # ⚠️ UPDATE
  service_manager: "0x..."      # ⚠️ UPDATE

wallet:
  address: "0x..."              # ⚠️ UPDATE (your wallet address)
```

### 2. Setup Wallet

If you don't have a wallet keystore:

```bash
# Create new wallet
python3 configs/make_wallet.py

# Enter passphrase when prompted
# Wallet will be saved to ~/.ros_eth/wallet.json
```

Or copy existing wallet:

```bash
mkdir -p ~/.ros_eth
cp /path/to/your/wallet.json ~/.ros_eth/wallet.json
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env
```

Update if needed (defaults usually work):

```bash
ROS_MASTER_URI=http://localhost:11311
WALLET_PATH=~/.ros_eth/wallet.json
ETH_WALLET_PASSPHRASE=           # Leave empty for prompt
```

### 4. Build and Start

```bash
./ros-eth-bridge-docker.sh build
./ros-eth-bridge-docker.sh start
```

Or manually:

```bash
docker compose up -d --build
```

### 5. Verify Running

```bash
# Check logs
./ros-eth-bridge-docker.sh logs

# Check ROS nodes
./ros-eth-bridge-docker.sh rosnode

# Check ROS topics
./ros-eth-bridge-docker.sh rostopic
```

## Configuration Files

### configs/dao.yaml (Main Configuration)

**Required updates before running:**

1. **Contract Addresses** (from deployment):
   ```yaml
   contracts:
     iecoin: "0x..."
     organization: "0x..."
     task_manager: "0x..."
     service_manager: "0x..."
   ```

2. **Wallet Address**:
   ```yaml
   wallet:
     address: "YourWalletAddress"
   ```

3. **RPC URLs** (if different from localhost):
   ```yaml
   chain:
     rpc_url: ws://YOUR_IP:8545
     http_fallback_url: http://YOUR_IP:8545
   ```

### configs/dao.yaml.template

Template file showing all configuration options with comments. Copy this to `dao.yaml` and customize.

### .env (Environment Variables)

Optional overrides for Docker environment. Usually defaults are fine.

## Where to Update Contract Addresses

**Primary Location:** `configs/dao.yaml` - Update the `contracts` section

**Find Addresses From:**

1. **Deployment artifacts:**
   ```bash
   cat ../../blockchain-network/smart-contracts/deployments/1337.json
   ```

2. **Deployment logs:** Check console output when running `deploy.js`

3. **Query blockchain:**
   ```bash
   # If you know the deployment TX hash
   cast tx $TX_HASH --rpc-url http://localhost:8545
   ```

## ROS Topics Published

When running, the bridge publishes these topics:

```bash
/dao/task_registered                # New task created
/dao/task_assigned                  # Task assigned to robot
/dao/task_verified                  # Task approved by oracle
/dao/task_rejected                  # Task rejected
/dao/service_registered             # New service available
/dao/service_busy_changed           # Service availability changed
```

## ROS Action Servers

Available action servers for robots:

```bash
/dao/register_service_action        # Register a robot service
/dao/register_task_action           # Create a new task
/dao/submit_proof_action            # Submit task completion proof
/dao/activate_task_action           # Activate a task
/dao/set_service_busy_action        # Change service availability
```

## Helper Script Commands

```bash
./ros-eth-bridge-docker.sh build     # Build image
./ros-eth-bridge-docker.sh start     # Start container
./ros-eth-bridge-docker.sh stop      # Stop container
./ros-eth-bridge-docker.sh restart   # Restart
./ros-eth-bridge-docker.sh logs      # View logs
./ros-eth-bridge-docker.sh shell     # Open bash shell
./ros-eth-bridge-docker.sh status    # Show status
./ros-eth-bridge-docker.sh rosnode   # List ROS nodes
./ros-eth-bridge-docker.sh rostopic  # List dao topics
./ros-eth-bridge-docker.sh check     # Check configuration
./ros-eth-bridge-docker.sh clean     # Remove container
./ros-eth-bridge-docker.sh rebuild   # Full rebuild
```

## Manual Docker Commands

### Build

```bash
docker build -t ros-eth-bridge:latest -f Dockerfile ..
```

### Run

```bash
docker run -d \
  --name ros-eth-bridge \
  --network host \
  -e ROS_MASTER_URI=http://localhost:11311 \
  -e ROS_IP=127.0.0.1 \
  -e ETH_WALLET_PASSPHRASE="" \
  -v "$(pwd)/configs/dao.yaml:/root/catkin_ws/src/ros_eth_bridge/config/dao.yaml:ro" \
  -v "$HOME/.ros_eth/wallet.json:/root/.ros_eth/wallet.json:ro" \
  ros-eth-bridge:latest
```
```

Now use `docker compose` for easier management.
