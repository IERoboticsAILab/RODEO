# Oracle Node

The Oracle Node is a trusted verification service that validates task completion proofs submitted by robots and interacts with the blockchain to approve or reject tasks.

## What the Oracle Does

The Oracle serves as an independent verification layer in the RODEO system:

1. **Listens for Proof Submissions** - Monitors blockchain events when robots submit task completion proofs
2. **Validates Proofs** - Analyzes proof data to verify task completion:
   - **ROS bag files (.bag)**: Validates robot motion, arm movements, and disposal events
   - **Power consumption logs (.csv)**: Calculates energy usage and converts to IECoin rewards
3. **Makes Decisions** - Approves valid proofs or rejects invalid ones with specific reasons
4. **Updates Blockchain** - Sends verification transactions to the TaskManager contract
5. **Triggers Payments** - Approved tasks automatically release escrowed funds to robots

### Current Validation Capabilities

#### ROS Bag Validation
The oracle analyzes robot behavior from ROS bag recordings:
- **Base Movement**: Tracks odometry to verify robot traveled minimum distance
- **Arm Manipulation**: Monitors joint states for arm activity
- **Disposal Events**: Confirms task-specific events (e.g., waste disposal)
- **Motion Analysis**: Detects movement vs. stopped states to prevent false proofs

#### Power Consumption Validation
For energy-based tasks:
- Parses CSV power logs with timestamps and wattage
- Calculates total energy consumption (kWh)
- Converts energy to IECoin rewards based on configured rate
- Awards tokens proportional to energy used

---

## Quick Start (Docker)

### Prerequisites
- Docker and Docker Compose
- Running blockchain (Ganache or other)
- Deployed smart contracts

### 1. Configure

```bash
cd oracle/docker

# Edit with your contract addresses
nano .env
```

Update these values from your smart contract deployment:
```bash
# Get addresses from blockchain-network/smart-contracts/deployments/1337.json
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...

# Oracle wallet (must be registered as oracle in contracts)
ORACLE_ADDRESS=0x...
ORACLE_PRIVATE_KEY=0x...
```

### 2. Build and Start

```bash
# Build the Docker image
./oracle-docker.sh build

# Start the oracle
./oracle-docker.sh start

# View logs
./oracle-docker.sh logs
```

### 3. Verify Running

Check the logs for successful startup:
```
rodeo-oracle  | ✅ Oracle configuration loaded from environment variables
rodeo-oracle  | Starting event watcher from block 0 (current: 172)
rodeo-oracle  |
rodeo-oracle  | [li] list inbox, [ok] approve, [no] reject, [va] validate, [q] quit: Watching oracle requests and outcomes

```
---

## How It Works

### Event Flow

```
┌─────────────────────────────────────────────────────┐
│ 1. Robot submits proof via ROS-ETH Bridge          │
│    TaskManager.submitProof(taskId, proofURI)       │
└────────────────┬────────────────────────────────────┘
                 │
                 │ ProofSubmitted event
                 ▼
┌─────────────────────────────────────────────────────┐
│ 2. Oracle detects event and retrieves proof        │
│    - Downloads .bag or .csv file                   │
│    - Validates proof data                          │
└────────────────┬────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
    ✅ Valid         ❌ Invalid
         │                │
         ▼                ▼
┌─────────────┐  ┌─────────────────┐
│ 3a. Approve │  │ 3b. Reject      │
│ verifyTask()│  │ rejectProof()   │
└──────┬──────┘  └────────┬────────┘
       │                   │
       ▼                   ▼
┌─────────────┐  ┌──────────────────┐
│ Task marked │  │ Task marked      │
│ as Verified │  │ as Rejected      │
│             │  │ (reason stored)  │
└──────┬──────┘  └────────┬─────────┘
       │                   │
       │ Escrowed         │ Escrowed
       │ funds            │ funds
       │ released to      │ returned to
       │ robot            │ creator
       ▼                   ▼
```

### Proof Format

**ROS Bag Files:**
```
Proof URI: file:///path/to/task_tid1_20250904_164349.bag
Topics:
  - /odom_mocap (nav_msgs/Odometry)
  - /vx300s/joint_states (sensor_msgs/JointState)
  - /disposal_event (std_msgs/String)
```

note: In the proofs directory there are two  examplaary proofs rosbags from task 1 (task_tid1_20250904_164349.bag) and task 10 (task_tid10_20250910_145742.bag).

❌ Task 1 is a failed task and will result in escrowed funds returend to creater.

✅ Task 2 is sucsesfull task and will result in escrowed funds relested to robot.

**Power CSV Files:**
```
Proof URI: file:///path/to/power_log.csv
Format:
timestamp,watts
1234567890.123,45.2
1234567890.223,46.8
...
```

---

## Interactive Mode

Attach to running oracle for interactive control:

```bash
docker attach rodeo-oracle
```

**Menu options:**
```
1. Check pending tasks (inbox)
2. Approve a task manually
3. Reject a task manually  
4. View task details
5. Exit
```

To detach without stopping: `Ctrl+P` then `Ctrl+Q`

---


---

## Usage Examples

### Manual Approval (if needed)

```bash
# Attach to oracle
docker attach rodeo-oracle

# Select option 2 (Approve task)
# Enter task ID when prompted
```

---

## Development

### Native Python (without Docker)

For development and testing:

```bash
cd oracle
pip install -r docker/requirements.txt

# Configure
cp addresses-ganache.json addresses.json
nano addresses.json

# Run
python -m oracle_node.main
```

📖 **See [oracle_node/README.md](oracle_node/README.md) for development documentation**

## Files and Directories

```
oracle/
├── docker/                    # Docker deployment
│   ├── Dockerfile             # Container definition
│   ├── docker-compose.yml     # Orchestration
│   ├── .env.example           # Configuration template
│   ├── oracle-docker.sh       # Helper script
│   ├── QUICKSTART.md          # Quick start guide
│   └── README.md              # Docker documentation
├── oracle_node/               # Oracle Python package
│   ├── main.py                # Entry point
│   ├── controller.py          # Validation logic
│   ├── events.py              # Event monitoring
│   ├── task_manager.py        # Contract interaction
│   └── validator/             # Validation modules
├── proofs/                    # Proof file storage
│   └── README.md              # Proof examples
├── oracle_rosbag_validator.py # ROS bag validator
├── power_logger.py            # Power monitoring utility
└── addresses.json             # Contract addresses (fallback)
```

---

## See Also

- **Docker Setup:** [docker/README.md](docker/README.md) - Detailed Docker configuration
- **Quick Start:** [docker/QUICKSTART.md](docker/QUICKSTART.md) - Fast setup guide
- **Oracle Module:** [oracle_node/README.md](oracle_node/README.md) - Development docs
- **Smart Contracts:** [../blockchain-network/smart-contracts/README.md](../blockchain-network/smart-contracts/README.md)

---

## License

MIT License
