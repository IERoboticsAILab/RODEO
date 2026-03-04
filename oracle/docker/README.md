# Oracle Node Docker Container

This directory contains the Docker configuration for running the RODEO Oracle Node in a containerized environment.

## Overview

The Oracle Node validates task proofs submitted by robots and interacts with the blockchain to approve or reject task completions. It runs in a ROS Noetic environment to support .bag file validation.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose V2 (use `docker compose`, not `docker-compose`)
- Access to the blockchain RPC endpoint (Ganache or other)
- Smart contract addresses from deployment

## Configuration

The oracle supports two configuration methods:

### Method 1: Environment Variables (.env file) - Recommended

1. Copy the example configuration:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your deployment details:
   ```bash
   # Smart Contract Addresses
   ORGANIZATION_ADDRESS=0xcEC91d876E8f003110D43381359b1bAd124e7F2b
   TASK_MANAGER_ADDRESS=0xF818A7C2AFC45cF4B9DDC48933C9A1edD624e46f
   SERVICE_MANAGER_ADDRESS=0x5370F78c6af2Da9cF6642382A3a75F9D5aEc9cc1
   IECOIN_ADDRESS=0x0B306BF915C4d645ff596e518fAf3F9669b97016
   
   # Oracle Wallet
   ORACLE_ADDRESS=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
   ORACLE_PRIVATE_KEY=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
   ```

3. **After deploying new contracts**, simply update the addresses in `.env` and restart:
   ```bash
   docker compose restart
   ```

### Method 2: addresses.json file

If environment variables are not set, the oracle falls back to `oracle/addresses.json`.

**See [CONFIG-UPDATE.md](CONFIG-UPDATE.md) for detailed configuration instructions.**

## Quick Start

### 1. Build the Docker Image

From the `oracle/docker` directory:

```bash
cd /home/lab/repos/robotic_decentralized_organization/oracle/docker
docker compose build
```

Or use the helper script:

```bash
./oracle-docker.sh build
```

### 2. Start the Oracle

```bash
docker compose up -d
# or
./oracle-docker.sh start
```

To view logs:

```bash
docker compose logs -f oracle
# or
./oracle-docker.sh logs
```

You should see:
```
✅ Oracle configuration loaded from environment variables
Watching oracle requests and outcomes...
```

### 3. Interact with the Oracle

Attach to the running container for interactive menu:

```bash
docker attach rodeo-oracle
```

Or execute commands directly:

```bash
docker exec -it rodeo-oracle python3 -m oracle_node.main
```

### 5. Stop the Oracle

```bash
docker-compose down
```

## Manual Docker Commands

### Build

```bash
docker build -t rodeo-oracle:latest \
  -f oracle/docker/Dockerfile \
  .
```

(Run from the repository root)

### Run Interactive

```bash
docker run -it --rm \
  --network host \
  -e RPC_URL=http://10.205.10.9:8545 \
  -e ADDRESSES_JSON=/workspace/addresses.json \
  -e BASE_ABI=/workspace/abi \
  -v $(pwd)/dao-bridge/ros-eth-bridge/catkin_ws/src/ros_eth_bridge/abi:/workspace/abi:ro \
  -v $(pwd)/oracle:/workspace/bags:ro \
  rodeo-oracle:latest
```

## Volume Mounts

- **ABI Files**: `/workspace/abi` - Contract ABI files (read-only)
- **Bag Files**: `/workspace/bags` - Directory containing .bag files for validation (read-only)
- **Addresses**: `/workspace/addresses.json` - Wallet and contract addresses configuration

## Oracle Menu Commands

Once attached to the container, you can use these interactive commands:

- `li` - List inbox (tasks waiting for validation)
- `ok` - Approve a task by ID
- `no` - Reject a task with reason
- `va` - Manually validate a task
- `q` - Quit the oracle

## Support

For issues or questions:
- Check the main RODEO documentation
- Review container logs: `docker-compose logs -f`
- Verify configuration with: `docker exec rodeo-oracle env`
