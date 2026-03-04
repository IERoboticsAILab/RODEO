# ROS-ETH Bridge - Quick Start Guide

## Prerequisites

- ✅ Docker and Docker Compose V2 installed
- ✅ ROS Master running (`roscore`)
- ✅ Blockchain running (Ganache at `ws://localhost:8545`)
- ✅ Smart contracts deployed

## Quick Start (4 Steps)

### Step 1: Get Contract Addresses

```bash
# View deployed contract addresses
cat /home/lab/repos/robotic_decentralized_organization/blockchain-network/smart-contracts/deployments/1337.json
```

You'll need:
- **IECoin** address
- **Organization** address
- **TaskManager** address  
- **ServiceManager** address

### Step 2: Update Configuration

Edit `configs/dao.yaml` with your contract addresses:

```bash
cd /home/lab/repos/robotic_decentralized_organization/dao-bridge/ros-eth-bridge/docker
nano configs/dao.yaml
```

**Update these sections:**

```yaml
contracts:
  iecoin: "0xYOUR_IECOIN_ADDRESS"
  organization: "0xYOUR_ORGANIZATION_ADDRESS"
  task_manager: "0xYOUR_TASKMANAGER_ADDRESS"
  service_manager: "0xYOUR_SERVICEMANAGER_ADDRESS"

wallet:
  address: "YOUR_WALLET_ADDRESS"
```

**Also check RPC URLs:**

```yaml
chain:
  rpc_url: ws://127.0.0.1:8545          # WebSocket endpoint
  http_fallback_url: http://127.0.0.1:8545  # HTTP endpoint
```

### Step 3: Setup Wallet (If Needed)

If you don't have `~/.ros_eth/wallet.json`:

```bash
python3 configs/make_wallet.py
# Enter passphrase when prompted
```

Or copy existing wallet:

```bash
mkdir -p ~/.ros_eth
cp /path/to/wallet.json ~/.ros_eth/wallet.json
```

**Get wallet address:**
```bash
cat ~/.ros_eth/wallet.json | jq -r '.address'
```

Update this address in `dao.yaml` wallet section.

### Step 4: Build and Start

```bash
# Check configuration
./ros-eth-bridge-docker.sh check

# Build image
./ros-eth-bridge-docker.sh build

# Start container
./ros-eth-bridge-docker.sh start

# View logs
./ros-eth-bridge-docker.sh logs
```

## Verify It's Working

### 1. Check Container Status

```bash
./ros-eth-bridge-docker.sh status
```

Should show `running` and `healthy`.

### 2. Check ROS Nodes

```bash
./ros-eth-bridge-docker.sh rosnode
```

Should show:
```
/dao_listener
/dao_writer
```

### 3. Check ROS Topics

```bash
./ros-eth-bridge-docker.sh rostopic
```

Should show topics like:
```
/dao/task_registered
/dao/task_assigned
/dao/service_registered
```

Or from host (if ROS is sourced):
```bash
rostopic list | grep dao
```

### 4. Test with Robot Emulator

```bash
cd /home/lab/repos/robotic_decentralized_organization/quick-start
python3 robot_emulator_demo.py
```

Should complete full workflow:
1. ✅ Service registration
2. ✅ Task creation (from web console)
3. ✅ Task assignment
4. ✅ Proof submission
5. ✅ Oracle validation

## Helper Commands

```bash
./ros-eth-bridge-docker.sh build     # Build Docker image
./ros-eth-bridge-docker.sh start     # Start bridge
./ros-eth-bridge-docker.sh stop      # Stop bridge
./ros-eth-bridge-docker.sh restart   # Restart bridge
./ros-eth-bridge-docker.sh logs      # View logs
./ros-eth-bridge-docker.sh shell     # Open bash shell
./ros-eth-bridge-docker.sh status    # Show status
./ros-eth-bridge-docker.sh rosnode   # List ROS nodes
./ros-eth-bridge-docker.sh rostopic  # List dao topics
./ros-eth-bridge-docker.sh check     # Check config
./ros-eth-bridge-docker.sh rebuild   # Full rebuild
```

## Common Issues

### ❌ "dao.yaml not found"

**Solution:**
```bash
# Copy from template if needed
cp configs/dao.yaml.template configs/dao.yaml
# Then edit with your addresses
nano configs/dao.yaml
```

### ❌ "Wallet file not found"

**Solution:**
```bash
# Create new wallet
python3 configs/make_wallet.py

# Or check .env WALLET_PATH
cat .env | grep WALLET_PATH
```

### ❌ "ROS Master not accessible"

**Solution:**
```bash
# Start roscore in separate terminal
roscore

# Or check ROS_MASTER_URI
echo $ROS_MASTER_URI
```

### ❌ "Cannot connect to blockchain"

**Check blockchain is running:**
```bash
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Should return current block number.**

If not running:
```bash
cd /home/lab/repos/robotic_decentralized_organization/blockchain-network/ganache-docker
docker compose up -d
```

### ❌ "Contract not found" or "Invalid contract"

**This means contract addresses in dao.yaml don't match deployed contracts.**

**Solution:**
1. Get actual addresses:
   ```bash
   cat ../../blockchain-network/smart-contracts/deployments/1337.json
   ```

2. Update `configs/dao.yaml` contracts section

3. Restart:
   ```bash
   ./ros-eth-bridge-docker.sh restart
   ```

### ❌ Bridge starts but no topics appear

**Check logs for errors:**
```bash
./ros-eth-bridge-docker.sh logs
```

**Common causes:**
- Wrong contract addresses
- Wallet can't unlock
- ROS Master connection issue

### ❌ "Cannot unlock wallet"

**Solution 1 - Set passphrase in .env:**
```bash
echo "ETH_WALLET_PASSPHRASE=your_password" >> .env
```

**Solution 2 - Use prompt method:**
In `dao.yaml`:
```yaml
wallet:
  unlock_method: prompt
```

Then start bridge with:
```bash
docker compose up
# Enter passphrase when prompted
```

## Configuration Tips

### Same Addresses as org-web?

The bridge needs the same contract addresses as the org-web console:

```bash
# Compare org-web config
cat /home/lab/repos/robotic_decentralized_organization/dao-bridge/org-web/backend/addresses.json

# Your bridge config
cat configs/dao.yaml
```

They should match!

### Use Template

If starting fresh:

```bash
# Start from template (has comments)
cp configs/dao.yaml.template configs/dao.yaml

# Edit with your values
nano configs/dao.yaml
```

### WebSocket vs HTTP

The bridge uses **WebSocket** (ws://) for event subscriptions and **HTTP** (http://) as fallback.

Both should point to same blockchain:
```yaml
chain:
  rpc_url: ws://localhost:8545
  http_fallback_url: http://localhost:8545
```

## Testing Workflow

### 1. Start All Components

```bash
# Terminal 1: Blockchain (if not running)
cd blockchain-network/ganache-docker
docker compose up

# Terminal 2: ROS Master
roscore

# Terminal 3: Bridge
cd dao-bridge/ros-eth-bridge/docker
./ros-eth-bridge-docker.sh start

# Terminal 4: org-web (optional, for task creation)
cd dao-bridge/org-web
./org-web-docker.sh start

# Terminal 5: Oracle (optional, for validation)
cd oracle/docker
./oracle-docker.sh start
```

### 2. Register Service (Robot Side)

```bash
cd quick-start
python3 robot_emulator_demo.py
```

Should output:
```
✅ Step 1: SERVICE REGISTERED!
   Service ID: 1
```

### 3. Create Task (Web Console)

Open http://localhost:8080
- Go to Tasks tab
- Click "Register New Task"
- Fill form and submit

### 4. Watch Assignment

Robot emulator should show:
```
🎯 Step 2: TASK ASSIGNED!
   Task ID: 1
```

### 5. Watch Execution and Validation

Robot completes task, submits proof, oracle validates.

## Updating After Redeployment

If you redeploy smart contracts:

```bash
# 1. Get new addresses
cat ../../blockchain-network/smart-contracts/deployments/1337.json

# 2. Update dao.yaml
nano configs/dao.yaml

# 3. Restart bridge (no rebuild needed)
./ros-eth-bridge-docker.sh restart
```

## Production Checklist

Before production deployment:

- [ ] Use secure wallet storage (Docker secrets)
- [ ] Set strong wallet passphrase
- [ ] Use wss:// for WebSocket RPC (encrypted)
- [ ] Increase transaction confirmations (≥3)
- [ ] Set resource limits in docker-compose.yml
- [ ] Configure log rotation
- [ ] Enable monitoring/alerts
- [ ] Test failover scenarios

## Next Steps

After bridge is running:

1. **Test robot integration** - Run robot_emulator_demo.py
2. **Create tasks** - Use org-web console
3. **Monitor events** - Watch bridge logs and ROS topics
4. **Deploy real robots** - Integrate actual hardware

## Support

- **Full docs**: [README.md](README.md)
- **Check config**: `./ros-eth-bridge-docker.sh check`
- **View logs**: `./ros-eth-bridge-docker.sh logs`
- **ROS topics**: `./ros-eth-bridge-docker.sh rostopic`

## Summary: Where to Update Contract Addresses

**File:** `configs/dao.yaml`

**Section:**
```yaml
contracts:
  iecoin: "0x..."              # ⬅️ UPDATE HERE
  organization: "0x..."         # ⬅️ UPDATE HERE
  task_manager: "0x..."         # ⬅️ UPDATE HERE
  service_manager: "0x..."      # ⬅️ UPDATE HERE
```

**Get addresses from:**
```bash
cat ../../blockchain-network/smart-contracts/deployments/1337.json
```

That's it! Update those 4 addresses and you're good to go.
