# Oracle Docker - Quick Start Guide

## Prerequisites Check

Before building, ensure you have:

1. ✅ Docker and Docker Compose installed
2. ✅ Blockchain running (Ganache at `http://localhost:8545` or update in `.env`)
3. ✅ Contract addresses configured (see Configuration below)
4. ✅ ABI files exist at `dao-bridge/ros-eth-bridge/catkin_ws/src/ros_eth_bridge/abi/`

## Configuration

### Option 1: Using .env File (Recommended)

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your contract addresses:
   ```bash
   nano .env
   ```

3. Update these critical values:
   ```bash
   # Smart Contract Addresses
   ORGANIZATION_ADDRESS=0x...
   TASK_MANAGER_ADDRESS=0x...
   SERVICE_MANAGER_ADDRESS=0x...
   IECOIN_ADDRESS=0x...
   
   # Oracle Wallet
   ORACLE_ADDRESS=0x...
   ORACLE_PRIVATE_KEY=0x...
   ```

See [CONFIG-UPDATE.md](CONFIG-UPDATE.md) for detailed configuration instructions.

### Option 2: Using addresses.json

If you don't create a `.env` file, the oracle will use `oracle/addresses.json`.

## Build and Run (3 Steps)

### Step 1: Build the Image

```bash
cd /home/lab/repos/robotic_decentralized_organization/oracle/docker
./oracle-docker.sh build
```

Or manually:
```bash
docker-compose build
```

**Build time**: ~5-10 minutes (downloads ROS Noetic base image)

### Step 2: Start the Oracle

```bash
./oracle-docker.sh start
```

Or manually:
```bash
docker-compose up -d
```

### Step 3: Check Status

```bash
./oracle-docker.sh logs
```

You should see:
```
Watching oracle requests and outcomes
[li] list inbox, [ok] approve, [no] reject, [va] validate, [q] quit:
```

## Interactive Usage

To interact with the oracle menu:

```bash
./oracle-docker.sh attach
```

**Available commands:**
- `li` - List tasks in inbox
- `va` - Validate a task by ID
- `ok` - Approve a task by ID
- `no` - Reject a task with reason
- `q` - Quit

**To detach without stopping**: Press `Ctrl+P` then `Ctrl+Q`

## Common Tasks

### View Live Logs

```bash
./oracle-docker.sh logs
```

Press `Ctrl+C` to exit log view.

### Restart Oracle

```bash
./oracle-docker.sh restart
```

### Stop Oracle

```bash
./oracle-docker.sh stop
```

### Open Shell in Container

```bash
./oracle-docker.sh exec
```

Or manually:
```bash
docker exec -it rodeo-oracle bash
```

### Complete Rebuild

```bash
./oracle-docker.sh rebuild
```

This will:
1. Stop and remove the container
2. Rebuild the image from scratch  
3. Start the new container

## Verify It's Working

### 1. Check Container is Running

```bash
docker ps | grep rodeo-oracle
```

### 2. Check Oracle Logs

```bash
docker logs rodeo-oracle
```

Look for:
- ✅ "Watching oracle requests and outcomes"
- ✅ Oracle menu prompt

### 3. Test Validation

1. Attach to container: `./oracle-docker.sh attach`
2. Type `li` to list inbox
3. If there are tasks, type `va` and enter a task ID

## Troubleshooting

### Build Fails

**Error**: "Cannot connect to Docker daemon"
```bash
sudo systemctl start docker
```

**Error**: "Dockerfile not found"
```bash
# Make sure you're in oracle/docker directory
cd /home/lab/repos/robotic_decentralized_organization/oracle/docker
```

### Container Won't Start

**Check logs:**
```bash
docker logs rodeo-oracle
```

**Common issues:**

1. **Port conflict**: Another service using port 11311 (ROS)
   - Solution: Stop other ROS instances or change `ROS_MASTER_URI`

2. **Missing ABI files**:
   ```
   Could not start watcher
   ```
   - Solution: Verify ABI path in docker-compose.yml
   - Check: `ls ../../dao-bridge/ros-eth-bridge/catkin_ws/src/ros_eth_bridge/abi/`

3. **Wrong RPC URL**:
   ```
   Connection refused
   ```
   - Solution: Update `RPC_URL` in docker-compose.yml to match your blockchain

### Event Watcher Not Working

If oracle doesn't automatically process proofs:

1. **Check the watcher started**:
   ```bash
   docker logs rodeo-oracle | grep "Watching"
   ```

2. **Manually validate tasks**:
   - Attach: `./oracle-docker.sh attach`
   - List: `li`
   - Validate: `va` then enter task ID

3. **Verify RPC connection**:
   ```bash
   docker exec rodeo-oracle python3 -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('http://10.205.10.9:8545')); print(f'Connected: {w3.is_connected()}')"
   ```

### Can't Attach to Container

**Error**: "Cannot attach to a stopped container"
```bash
./oracle-docker.sh start  # Start it first
./oracle-docker.sh attach
```

**Detach without stopping**: `Ctrl+P` then `Ctrl+Q` (not `Ctrl+C`)

## Configuration

To change settings, edit `docker-compose.yml`:

```yaml
environment:
  - RPC_URL=http://YOUR_BLOCKCHAIN_IP:8545
  - MIN_GAS_PRICE=2000000000  # 2 gwei
  - GAS_MULTIPLIER=1.5
```

Then restart:
```bash
./oracle-docker.sh restart
```

## Next Steps

1. **Test end-to-end**:
   - Create a task via web GUI
   - Submit proof via robot emulator
   - Watch oracle auto-validate

2. **Production deployment**:
   - See full README.md for production settings
   - Configure secrets management
   - Set up monitoring and alerts

3. **Multiple oracles**:
   - Copy docker-compose.yml
   - Change container name
   - Use different wallet addresses

## Helper Script Commands

```bash
./oracle-docker.sh build     # Build image
./oracle-docker.sh start     # Start container
./oracle-docker.sh stop      # Stop container
./oracle-docker.sh restart   # Restart container
./oracle-docker.sh logs      # View logs
./oracle-docker.sh attach    # Interactive menu
./oracle-docker.sh exec      # Open shell
./oracle-docker.sh status    # Show status
./oracle-docker.sh clean     # Remove container
./oracle-docker.sh rebuild   # Full rebuild
```

## Support

- **Full documentation**: See `README.md` in this directory
- **Check logs**: `./oracle-docker.sh logs`
- **Test connection**: `./oracle-docker.sh exec` then test Python imports
