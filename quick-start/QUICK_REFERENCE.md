# RODEO Demo - Quick Reference

Fast reference for running the complete RODEO integration demo.

## Prerequisites Check

```bash
# Verify installations
docker --version          # Docker 20+
node --version           # Node.js 22+
python3 --version        # Python 3.8+
rosversion -d            # ROS Noetic

# Clone and navigate
cd /path/to/robotic_decentralized_organization
```

## Quick Start (6 Steps)

### 1. Start Ganache (Terminal 1)
```bash
cd blockchain-network/ganache-docker
docker-compose up -d
docker logs -f ganache
# ✅ Wait for: "Listening on 0.0.0.0:8545"
```

### 2. Deploy Contracts (Terminal 1)
```bash
cd blockchain-network/smart-contracts
npm install
npx hardhat run scripts/deploy.js --network localhost

# 📝 Save addresses from output - REQUIRED for next steps
cat deployments/1337.json
```

**⚠️ IMPORTANT:** Contract addresses change on every deployment!

### 3. Configure ROS-ETH Bridge (Terminal 2)

**BEFORE starting the bridge, update contract addresses:**

```bash
cd dao-bridge/ros-eth-bridge/catkin_ws/src/ros_eth_bridge

# Edit config/dao.yaml and replace contract addresses with values from:
# blockchain-network/smart-contracts/deployments/1337.json
# 
# Update these fields:
#   contracts.iecoin: "0x..."        (from deployments/1337.json)
#   contracts.organization: "0x..."  (from deployments/1337.json)
#   contracts.task_manager: "0x..." (from deployments/1337.json)
#   contracts.service_manager: "0x..." (from deployments/1337.json)

nano config/dao.yaml  # or vim/code
```

**After updating dao.yaml, build and start:**

```bash
cd dao-bridge/ros-eth-bridge/catkin_ws
catkin_make
source devel/setup.bash

# Terminal 2a - ROS Core
roscore

# Terminal 2b - Bridge
source devel/setup.bash
roslaunch ros_eth_bridge ros_eth_gateway.launch
# ✅ Wait for: "dao_writer ready"
```

### 4. Start Oracle (Terminal 3)

**⚠️ UPDATE oracle_node/addresses.json first:**

```bash
cd oracle

# Edit oracle_node/addresses.json and update contract addresses from:
# blockchain-network/smart-contracts/deployments/1337.json
nano oracle_node/addresses.json

# Then set environment and start:
export RPC_URL="http://localhost:8545"
export ADDRESSES_JSON="oracle_node/addresses.json"
export BASE_ABI="../blockchain-network/smart-contracts/artifacts/contracts"

python3 -m oracle_node.main
# ✅ Wait for: "Watching oracle requests and outcomes"
```

### 5. Start Robot Emulator (Terminal 4)
```bash
cd quick-start
source ../dao-bridge/ros-eth-bridge/catkin_ws/devel/setup.bash
./robot_emulator_demo.py
# ✅ Wait for: "Robot is ready and listening"
```

### 6. Start Web Console (Browser)

**⚠️ UPDATE backend/addresses.json first:**

```bash
# Terminal 5
cd dao-bridge/org-web

# Edit backend/addresses.json and update contract addresses from:
# blockchain-network/smart-contracts/deployments/1337.json
nano backend/addresses.json

# Configure backend/addresses.json
docker build -t org-console .
docker run --rm -p 8080:80 --network host org-console

# Open: http://localhost:8080
```

## Demo Flow

1. **Web Console** → Create Task (100 IEC reward)
2. **Robot** → Auto-assigned, executes (10s)
3. **Robot** → Submits proof (CSV)
4. **Oracle** → Validates proof
5. **Blockchain** → Transfers 100 IEC to robot
6. **Done!** ✅

## Configuration Templates

**⚠️ IMPORTANT:** The addresses shown below are EXAMPLES from a previous deployment.  
**YOU MUST REPLACE THEM** with actual addresses from `blockchain-network/smart-contracts/deployments/1337.json` after running deploy.js!

### dao.yaml (ROS Bridge)
```yaml
chain:
  rpc_url: ws://localhost:8545
  chain_id: 1337
contracts:
  iecoin: "0x5FbDB2315678afecb367f032d93F642f64180aa3"          # ⚠️ REPLACE
  organization: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"     # ⚠️ REPLACE
  task_manager: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"     # ⚠️ REPLACE
  service_manager: "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9"   # ⚠️ REPLACE
wallet:
  address: "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"  # Robot (stays same)
```

### addresses.json (Oracle)
```json
{
  "contracts": {
    "TaskManager": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"  // ⚠️ REPLACE
  },
  "wallets": {
    "oracle": {
      "public": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",   // Account 2 (stays same)
      "private": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
    }
  }
}
```

### addresses.json (Web Console)
```json
{
  "rpc_url": "http://localhost:8545",
  "contracts": {
    "Organization": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"  // ⚠️ REPLACE
  },
  "wallets": {
    "organization": {
      "public": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",   // Account 4 (stays same)
      "private": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
    }
  }
}
```

## Troubleshooting

### Ganache issues
```bash
docker-compose down
rm -rf ganache_db/
docker-compose up -d
```

### Bridge connection fails
```bash
# Check Ganache
curl http://localhost:8545 -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Check ROS
rostopic list | grep /dao
```

### Oracle not receiving events
```bash
# Verify oracle address matches TaskManager
cd blockchain-network/smart-contracts
npx hardhat console --network localhost
> const org = await ethers.getContractAt("Organization", "ADDRESS")
> const tm = await ethers.getContractAt("TaskManager", await org.taskManager())
> await tm.oracle()
```

### Robot doesn't get assigned
```bash
# Check service registered
rosservice call /dao/get_all_services

# Check robot has IEC for gas
# Should have 2000 IEC from deployment
```

## Verification Commands

```bash
# Check balances
npx hardhat console --network localhost
> const iec = await ethers.getContractAt("IECoin", "0x5FbDB...")
> await iec.balanceOf("0x9965...") // Robot address
> ethers.formatEther(await iec.balanceOf("0x9965..."))

# Check task status
rosservice call /dao/get_all_tasks

# Check services
rosservice call /dao/get_all_services
```

## Expected Output

### Robot Emulator
```
✅ Service registered successfully!
🎯 TASK ASSIGNED!
   Task ID: 1
   Reward: 100 IEC
🤖 Executing task...
📤 Submitting proof...
✅ Proof submitted successfully!
```

### Oracle
```
Starting validation for task 1
Task 1 CSV summary
Energy kWh: 0.000575000
✅ Task 1 verified
```

### Web Console
```
Task Status: Verified ✅
Executor: 0x9965...
Reward: 100 IEC
```

## Terminal Layout

```
┌─────────────────┬─────────────────┬─────────────────┐
│   Terminal 1    │   Terminal 2    │   Terminal 3    │
│                 │                 │                 │
│   Ganache       │   ROS Bridge    │   Oracle        │
│   (Docker)      │   (ROS Node)    │   (Python)      │
│                 │                 │                 │
│ docker-compose  │ roslaunch       │ python3 -m      │
│ up -d           │ ros_eth_bridge  │ oracle_node     │
│                 │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
┌─────────────────┬─────────────────────────────────────┐
│   Terminal 4    │         Browser                     │
│                 │                                     │
│   Robot         │   Web Console                       │
│   (Python+ROS)  │   http://localhost:8080             │
│                 │                                     │
│ ./robot_        │   [Create Task Button]              │
│ emulator_demo.py│                                     │
└─────────────────┴─────────────────────────────────────┘
```

## Demo Success Checklist

- [ ] Ganache running (20 accounts visible)
- [ ] Contracts deployed (4 addresses in deployments/1337.json)
- [ ] ROS bridge connected (topics visible with `rostopic list`)
- [ ] Oracle watching (menu prompt visible)
- [ ] Robot service registered (TX hash printed)
- [ ] Web console accessible (localhost:8080 loads)
- [ ] Task created (visible in web console)
- [ ] Robot receives assignment (logs show task ID)
- [ ] Proof submitted (TX hash printed)
- [ ] Oracle validates (success message)
- [ ] Tokens transferred (robot balance increased)

## Next Steps

- Try multiple robots with different services
- Test rejection by submitting invalid proofs
- Monitor gas costs for operations
- Scale to public testnet (Sepolia)

Full tutorial: [TUTORIAL_FULL_DEMO.md](TUTORIAL_FULL_DEMO.md)
