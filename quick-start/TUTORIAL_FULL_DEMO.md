# RODEO Full Integration Demo Tutorial

Complete end-to-end demonstration of the RODEO system: Task creation → Service registration → Assignment → Proof submission → Oracle verification → Token transfer.

## Prerequisites

- Docker and Docker Compose
- Node.js 22+
- Python 3.8+
- ROS Noetic (for robot emulator)

## Architecture Overview

```
User (org-web) → TaskManager → Robot (ros-eth-bridge) → Oracle → TokenTransfer
     ↓              ↓              ↓                      ↓           ↓
  Creates Task   Stakes IEC   Submits Proof        Validates    Releases IEC
```

---

## Step 1: Start Ganache (Local Blockchain)

```bash
cd blockchain-network/ganache-docker
docker-compose up -d

# Verify it's running
docker logs ganache

# You should see 20 accounts with 1000 ETH each
# RPC endpoint: http://localhost:8545
```

**Key Accounts (from ganache_keys.txt):**
- Account 0 (Deployer): `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`
- Account 1 (Org Owner): `0x70997970C51812dc3A010C7d01b50e0d17dc79C8`
- Account 2 (Oracle): `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC`
- Account 3 (Human/User): `0x90F79bf6EB2c4f870365E785982E1f101E93b906`
- Account 4 (Organization): `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65`
- Account 5 (Robot): `0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc`

---

## Step 2: Deploy Smart Contracts

```bash
cd blockchain-network/smart-contracts

# Install dependencies (if not done)
npm install

# Deploy contracts to Ganache
npx hardhat run scripts/deploy.js --network localhost
```

**Verify deployment:**
```bash
cat deployments/1337.json
```

You should see contract addresses for:
- IECoin
- Organization
- TaskManager
- ServiceManager

**Important:** The deploy script automatically:
1. Sets account 2 as the oracle address
2. Transfers 2000 IEC to accounts 3, 4, and 5 (human, org, robot)

**⚠️ CRITICAL:** Contract addresses are generated fresh on EVERY deployment!

**Save these addresses** - you'll need them for the next steps:
```bash
# Copy the addresses from this file:
cat deployments/1337.json
```

Example output:
```json
{
  "contracts": {
    "IECoin": { "address": "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
    "Organization": { "address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512" },
    "ServiceManager": { "address": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9" },
    "TaskManager": { "address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0" }
  }
}
```

---

## Step 3: Configure ROS-ETH Bridge

**⚠️ YOU MUST UPDATE CONTRACT ADDRESSES BEFORE STARTING THE BRIDGE!**

Navigate to bridge configuration:

```bash
cd dao-bridge/ros-eth-bridge/catkin_ws/src/ros_eth_bridge
```

**Edit `config/dao.yaml` with addresses from Step 2:**
```yaml
chain:
  rpc_url: ws://localhost:8545
  http_fallback_url: http://localhost:8545
  chain_id: 1337

contracts:
  iecoin: "0x5FbDB2315678afecb367f032d93F642f64180aa3"        # ⚠️ REPLACE with address from deployments/1337.json
  organization: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"   # ⚠️ REPLACE with address from deployments/1337.json
  task_manager: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"   # ⚠️ REPLACE with address from deployments/1337.json
  service_manager: "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9" # ⚠️ REPLACE with address from deployments/1337.json

abi_paths:
  iecoin: "/path/to/ros_eth_bridge/abi/IECoin.json"
  organization: "/path/to/ros_eth_bridge/abi/Organization.json"
  task_manager: "/path/to/ros_eth_bridge/abi/TaskManager.json"
  service_manager: "/path/to/ros_eth_bridge/abi/ServiceManager.json"

wallet:
  keystore_path: ~/.ros_eth/wallet.json
  unlock_method: prompt
  address: "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"  # Account 5 (Robot)

transaction:
  confirmations: 1
  max_retries: 5
  gas_limit: 3000000
  gas_multiplier: 1.3
```

**Create robot wallet keystore:**
```bash
# Create directory
mkdir -p ~/.ros_eth

# Create wallet.json with robot private key
cat > ~/.ros_eth/wallet.json << 'EOF'
{
  "version": 3,
  "id": "robot-wallet",
  "address": "9965507d1a55bcc2695c58ba16fb37d819b0a4dc",
  "crypto": {
    "cipher": "aes-128-ctr",
    "ciphertext": "robot_private_key_here",
    "kdf": "scrypt"
  }
}
EOF
```

**Note:** For testing, you can use unencrypted key: `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a` (Account 5)

**Build and launch bridge:**
```bash
cd dao-bridge/ros-eth-bridge/catkin_ws
catkin_make
source devel/setup.bash

# Start ROS core in separate terminal
roscore

# Launch bridge (in another terminal)
source devel/setup.bash
roslaunch ros_eth_bridge ros_eth_gateway.launch
```

**Verify bridge is running:**
```bash
# Check topics
rostopic list | grep /dao

# Should see:
# /dao/task_registered
# /dao/task_assigned
# /dao/service_registered
# etc.
```

---

## Step 4: Configure and Start Oracle

**⚠️ UPDATE CONTRACT ADDRESSES in oracle configuration:**

```bash
cd oracle
```

**Edit `oracle_node/addresses.json` with addresses from Step 2:**
```json
{
  "contracts": {
    "IECoin": "0x5FbDB2315678afecb367f032d93F642f64180aa3",        # ⚠️ REPLACE
    "Organization": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",   # ⚠️ REPLACE
    "ServiceManager": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9", # ⚠️ REPLACE
    "TaskManager": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"    # ⚠️ REPLACE
  },
  "wallets": {
    "oracle": {
      "public": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
      "private": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
    }
  }
}
```

**Set environment variables:**
```bash
export RPC_URL="http://localhost:8545"
export ADDRESSES_JSON="oracle_node/addresses.json"
export BASE_ABI="../blockchain-network/smart-contracts/artifacts/contracts"
```

**Start oracle:**
```bash
cd oracle
python3 -m oracle_node.main
```

**Verify oracle:**
- You should see: "Watching oracle requests and outcomes"
- Interactive menu appears: `[li] list inbox, [ok] approve, [no] reject, [va] validate, [q] quit:`

---

## Step 5: Configure and Start Web Console

**⚠️ UPDATE CONTRACT ADDRESSES in web console configuration:**

```bash
cd dao-bridge/org-web
```

**Edit `backend/addresses.json` with addresses from Step 2:**
```json
{
  "rpc_url": "http://localhost:8545",
  "contracts": {
    "Organization": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",   # ⚠️ REPLACE
    "IECoin": "0x5FbDB2315678afecb367f032d93F642f64180aa3",        # ⚠️ REPLACE
    "TaskManager": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",    # ⚠️ REPLACE
    "ServiceManager": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9"  # ⚠️ REPLACE
  },
  "wallets": {
    "organization": {
      "public": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
      "private": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
    }
  },
  "abi_root": "../../blockchain-network/smart-contracts/artifacts/contracts"
}
```

**Create `.env` file:**
```bash
cat > .env << 'EOF'
NEXT_PUBLIC_API_BASE=http://localhost:8080
EOF
```

**Build and run:**
```bash
# Build Docker image
docker build -t org-console .

# Run container
docker run --rm -p 8080:80 --network host org-console
```

**Access web console:**
- Open browser: `http://localhost:8080`
- You should see the Organization Console dashboard

---

## Step 6: Run End-to-End Demo

### Terminal Setup (5 terminals needed):

1. **Terminal 1:** Ganache (already running)
2. **Terminal 2:** ROS-ETH Bridge
3. **Terminal 3:** Oracle
4. **Terminal 4:** Robot Emulator (new)
5. **Terminal 5:** Web Console (browser)

### Create Robot Emulator Script

```bash
cd quick-start
```

Create `robot_emulator_demo.py`:

```python
#!/usr/bin/env python3
"""
Robot emulator for RODEO demo.
Registers service, monitors task assignments, submits proof.
"""

import rospy
import time
import tempfile
import actionlib
from ros_eth_msgs.msg import (
    RegisterServiceAction, RegisterServiceGoal,
    SubmitProofAction, SubmitProofGoal
)
from ros_eth_msgs.msg import TaskAssignment
from std_msgs.msg import String

class RobotEmulator:
    def __init__(self):
        rospy.init_node('robot_emulator_demo')
        
        # Action clients
        self.register_service_client = actionlib.SimpleActionClient(
            '/dao/register_service_action', RegisterServiceAction
        )
        self.submit_proof_client = actionlib.SimpleActionClient(
            '/dao/submit_proof_action', SubmitProofAction
        )
        
        # Wait for action servers
        rospy.loginfo("Waiting for action servers...")
        self.register_service_client.wait_for_server(timeout=rospy.Duration(30))
        self.submit_proof_client.wait_for_server(timeout=rospy.Duration(30))
        rospy.loginfo("Action servers connected!")
        
        # Subscribe to task assignments
        rospy.Subscriber('/dao/task_assigned', TaskAssignment, self.on_task_assigned)
        
        self.assigned_tasks = []
        
    def register_service(self):
        """Register delivery service"""
        rospy.loginfo("Registering delivery service...")
        
        goal = RegisterServiceGoal()
        goal.name = "Delivery Service"
        goal.description = "Package delivery robot"
        goal.category = "Logistics"
        goal.service_type = "ItemTransport"
        goal.price = "100"  # 100 IEC
        goal.provider_type = 0  # Robot provider
        goal.min_confirmations = 1
        
        self.register_service_client.send_goal(goal)
        self.register_service_client.wait_for_result(timeout=rospy.Duration(60))
        
        result = self.register_service_client.get_result()
        if result and result.success:
            rospy.loginfo(f"✅ Service registered! TX: {result.tx_hash}")
        else:
            rospy.logerr("❌ Service registration failed")
    
    def on_task_assigned(self, msg):
        """Handle task assignment"""
        rospy.loginfo(f"📋 Task {msg.task_id} assigned to us!")
        rospy.loginfo(f"   Reward: {msg.reward} IEC")
        rospy.loginfo(f"   Executor: {msg.executor}")
        
        self.assigned_tasks.append(msg.task_id)
        
        # Simulate task execution
        rospy.loginfo("🤖 Executing task (simulated 10 seconds)...")
        time.sleep(10)
        
        # Submit proof
        self.submit_proof(msg.task_id)
    
    def submit_proof(self, task_id):
        """Submit task completion proof"""
        rospy.loginfo(f"📤 Submitting proof for task {task_id}...")
        
        # Create dummy CSV proof file
        proof_file = f"/tmp/task_{task_id}_proof.csv"
        with open(proof_file, 'w') as f:
            f.write("timestamp_iso,current,voltage,power\\n")
            f.write("2026-03-03T10:00:00Z,0.5,230,115\\n")
            f.write("2026-03-03T10:00:01Z,0.5,230,115\\n")
            f.write("2026-03-03T10:00:02Z,0.5,230,115\\n")
        
        goal = SubmitProofGoal()
        goal.task_id = task_id
        goal.proof_uri = f"file://{proof_file}"
        goal.min_confirmations = 1
        
        self.submit_proof_client.send_goal(goal)
        self.submit_proof_client.wait_for_result(timeout=rospy.Duration(60))
        
        result = self.submit_proof_client.get_result()
        if result and result.success:
            rospy.loginfo(f"✅ Proof submitted! TX: {result.tx_hash}")
        else:
            rospy.logerr("❌ Proof submission failed")
    
    def run(self):
        """Main execution loop"""
        # Step 1: Register service
        self.register_service()
        
        rospy.loginfo("🎯 Robot ready! Waiting for task assignments...")
        rospy.loginfo("   Create a task via org-web console to trigger assignment")
        
        # Keep running
        rospy.spin()

if __name__ == '__main__':
    try:
        robot = RobotEmulator()
        robot.run()
    except rospy.ROSInterruptException:
        pass
```

Make it executable:
```bash
chmod +x robot_emulator_demo.py
```

### Execute Demo Flow

**Terminal 4 - Start Robot Emulator:**
```bash
cd quick-start
source ../dao-bridge/ros-eth-bridge/catkin_ws/devel/setup.bash
./robot_emulator_demo.py
```

You should see:
```
✅ Service registered! TX: 0x...
🎯 Robot ready! Waiting for task assignments...
```

**Terminal 5 - Web Console (Browser):**

1. Open `http://localhost:8080`
2. Navigate to **Tasks** page
3. Click **"Register New Task"**
4. Fill in:
   - Description: "Package delivery"
   - Category: "Logistics"
   - Task Type: "ItemTransport"
   - Reward: 100 IEC
5. Click **Submit**

**Watch the magic happen:**

1. **Terminal 2 (ROS Bridge):** Task registered event appears
2. **Terminal 4 (Robot):** Task assignment detected
   ```
   📋 Task 1 assigned to us!
      Reward: 100 IEC
   🤖 Executing task (simulated 10 seconds)...
   📤 Submitting proof for task 1...
   ✅ Proof submitted!
   ```
3. **Terminal 3 (Oracle):**
   ```
   Starting validation for task 1
   Task 1 CSV summary
   Energy kWh: 0.000057500
   IEC to award: 0.000057500 IEC
   ✅ Task 1 verified
   ```
4. **Web Console:** Task status changes to "Verified"

**Verify token transfer:**
```bash
# Check robot balance increased by 100 IEC
cd blockchain-network/smart-contracts
npx hardhat console --network localhost

> const IECoin = await ethers.getContractAt("IECoin", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
> await IECoin.balanceOf("0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc")
// Should show 2100 IEC (2000 initial + 100 reward)
```

---

## Troubleshooting

### Ganache not accessible
```bash
docker logs ganache
# Make sure it's listening on 0.0.0.0:8545
```

### ROS bridge fails to connect
```bash
# Check Ganache is running
curl http://localhost:8545 -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### Oracle doesn't receive requests
```bash
# Verify oracle address in TaskManager
cd blockchain-network/smart-contracts
npx hardhat console --network localhost
> const org = await ethers.getContractAt("Organization", "0x...")
> const tm = await ethers.getContractAt("TaskManager", await org.taskManager())
> await tm.oracle()
// Should match oracle wallet address
```

### Robot doesn't receive assignments
```bash
# Check service is active
rostopic echo /dao/service_registered -n 1

# Check robot balance (needs IEC for gas)
# Should have 2000 IEC from deployment
```

---

## Next Steps

1. **Modify task requirements** in web console
2. **Add multiple robots** with different services
3. **Test rejection scenarios** by submitting invalid proofs
4. **Monitor gas costs** for each operation
5. **Scale to public testnet** (Sepolia, Mumbai)

---

## System Architecture

```
┌──────────────┐
│   org-web    │ User creates task (stakes 100 IEC)
│  localhost   │
│   :8080      │
└──────┬───────┘
       │ HTTP POST /tasks/register
       ↓
┌──────────────────────────────────────┐
│         Ganache (localhost:8545)      │
│  ┌────────────────────────────────┐  │
│  │  TaskManager.sol               │  │
│  │  - Task created (ID: 1)        │  │
│  │  - 100 IEC staked              │  │
│  │  - Event: TaskRegistered       │  │
│  └────────────────────────────────┘  │
└──────┬───────────────────────────────┘
       │ Event listening
       ↓
┌──────────────┐        ┌──────────────┐
│ ros-eth-     │        │    robot     │
│   bridge     │        │  emulator    │
│ dao_listener │◄───────┤              │
└──────┬───────┘        └──────┬───────┘
       │ Publish           ROS  │
       │ /dao/task_registered   │
       └────────────────────────┘
               │
               ↓ Task assignment logic
         Auto-assigns to robot service
               │
┌──────────────▼───────────────────────┐
│  TaskManager.assignTask()            │
│  - Executor: robot address           │
│  - Event: TaskAssigned               │
└──────┬───────────────────────────────┘
       │ Event listening
       ↓
┌──────────────┐
│    robot     │ Receives assignment
│  emulator    │ Executes task (10s)
│              │ Submits proof (CSV)
└──────┬───────┘
       │ ROS action: /dao/submit_proof_action
       ↓
┌──────────────┐
│ ros-eth-     │ TX: submitProof()
│   bridge     │
│ dao_writer   │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────┐
│  TaskManager.submitProofAsExecutor() │
│  - Proof URI: file:///tmp/...csv    │
│  - Event: TaskOracleRequested        │
└──────┬───────────────────────────────┘
       │ Event listening
       ↓
┌──────────────┐
│    oracle    │ Receives request
│  oracle_node │ Validates CSV proof
│              │ TX: approve(taskId)
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────┐
│  TaskManager.approveTaskAsOracle()   │
│  - Verify oracle signature           │
│  - Transfer 100 IEC → robot          │
│  - Event: TaskVerified               │
└──────────────────────────────────────┘
       │
       ✅ Demo completed!
       Robot balance: 2100 IEC (+100)
```

---

## Demo Complete! 🎉

You've successfully run a complete RODEO workflow:
- ✅ Blockchain deployed (Ganache)
- ✅ Task created with staked tokens
- ✅ Robot service registered
- ✅ Automatic task assignment
- ✅ Proof submitted by robot
- ✅ Oracle validation
- ✅ Token transfer completed

This demonstrates the core value proposition of RODEO: **Trustless, automated coordination between humans and robots using blockchain-based smart contracts.**
