<h1 align="center">
RODEO: Robotic Decentralized Organization
</h1>

<!--

<a href="PROJECT_PAGE">
<img src="https://img.shields.io/badge/Homepage-blue?style=for-the-badge&logo=google-chrome&logoColor=white">
</a>
-->
<p align="center">
<a href="https://arxiv.org/abs/2603.06058">
<img src="https://img.shields.io/badge/arXiv-2603.06058-b31b1b?style=flat-square&logo=arxiv&logoColor=white">
</a>

<a href="https://youtu.be/L5voOWKFLzk?si=cIMpkU0fx8_hpq45">
<img src="https://img.shields.io/badge/Demo-Video-cc0000?style=flat&logo=youtube&logoColor=white">
</a>

<a href="LICENSE_LINK">
<img src="https://img.shields.io/badge/License-MIT-black?style=flat-square">
</a>
</p>



<p align="center">
<img src="assets/demo.gif" width="800">
</p>

---

This repository contains the complete implementation of RODEO (Robotic Decentralized Organization), a blockchain-based framework
that integrates trust and accountability mechanisms for robots. This work demonstrates how distributed ledger technology (DLT) can enable trustless, transparent, and autonomous task allocation in multi-robot systems.

## Abstract

RODEO presents a novel architecture that integrates Robot Operating System (ROS) with Ethereum blockchain smart contracts to create a decentralized autonomous organization (DAO) for robotic task management. This repo provides:

- **RODEO Smart Contracts**: RODEOs Smart contracts that are used to define the specific rules on how the organization is governed.
- **DAO bridge**: A programmable interface that allows robots and organizations to directly broadcast their operational needs and advertise their specific capabilities to the rest of the participants.
- **Verification Oracle**: A system component used ti verify that the robots physical actions (e.g., paths, sensor data), actually met the task specifications before the on-chain verdict triggers the release of the escrows.

## Repository Structure

```
robotic_decentralized_organization/
│
├── blockchain-network/        # Blockchain infrastructure
│   ├── smart-contracts/       # Solidity smart contracts, tests, deployment
│   └── ganache-docker/        # Local Ethereum blockchain (Ganache)
│
├── dao-bridge/                # ROS-Blockchain integration layer
│   ├── ros-eth-bridge/        # Bidirectional ROS-Ethereum communication
│   └── org-web/               # Web console for DAO management
│
├── oracle/                    # Task verification oracle
│
└── quick-start/               # Demo scripts and tutorials
```

## Quick Start Guide

This guide demonstrates the complete RODEO workflow using Docker containers.

### Prerequisites

- **Docker** (version 20.10+) with Docker Compose V2
- **Linux** environment (tested on Ubuntu 20.04+)
- **Git** for cloning the repository
- At least **8GB RAM** and **20GB disk space**

### Step 1: Start Blockchain Network

Launch the local Ganache blockchain:

```bash
cd blockchain-network/ganache-docker
docker compose up -d

# Verify blockchain is running
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Expected output**: `{"jsonrpc":"2.0","id":1,"result":"0x0"}`

### Step 2: Deploy Smart Contracts

Deploy the RODEO smart contracts to the local blockchain using Docker:

```bash
cd blockchain-network/smart-contracts/docker
./deploy.sh
```

To force a rebuild of the deployer image (e.g. after contract changes):

```bash
./deploy.sh --rebuild
```

**Important**: After deployment completes, note the contract addresses displayed in the output. You will need to update these addresses in all components.

**Sample output**:
```
IECoin deployed to: 0x3Aa5ebB10DC797CAC828524e59A333d0A371443c
Organization deployed to: 0x093e8F4d8f267d2CeEc9eB889E2054710d187beD
ServiceManager deployed to: 0xBa3e08b4753E68952031102518379ED2fDADcA30
TaskManager deployed to: 0xa85b028984bC54A2a3D844B070544F59dDDf89DE
```

The deployment addresses are automatically saved to `deployments/1337.json`.

### Step 3: Update Contract Addresses in All Components

#### Quick Update Script (Optional)

For convenience, you can use this script to update all components at once:

```bash
# From repository root
./scripts/update-addresses.sh blockchain-network/smart-contracts/deployments/1337.json
```

Or see [DEPLOYMENT-CONFIG.md](DEPLOYMENT-CONFIG.md) for manual update instructions.

**⚠️ CRITICAL**: After deployment, you must update the smart contract addresses in the following locations:

#### 3.1 Update Oracle Configuration

```bash
cd oracle/docker
nano .env
```

Update these variables with your deployed addresses:
```bash
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...
```

**Reference**: See [oracle/docker/CONFIG-UPDATE.md](oracle/docker/CONFIG-UPDATE.md) for details.

#### 3.2 Update Web Console Configuration

```bash
cd dao-bridge/org-web
nano .env
```

Update these variables:
```bash
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...
```

#### 3.3 Update ROS-Ethereum Bridge Configuration

```bash
cd ros-eth-bridge/docker/configs
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

**Reference**: See [dao-bridge/ros-eth-bridge/docker/CONFIG-UPDATE.md](dao-bridge/ros-eth-bridge/docker/CONFIG-UPDATE.md) for details.

### Step 4: Start Oracle Node

The oracle validates task completion proofs:

```bash
cd oracle/docker
docker compose up -d

# Verify oracle is running
docker logs rodeo-oracle --tail 20
```

**Expected output**:
```
✅ Oracle configuration loaded from environment variables
Starting event watcher from block 0 (current: X)
Watching oracle requests and outcomes
```

**Reference**: [oracle/docker/README.md](oracle/docker/README.md)

### Step 5: Start ROS-Ethereum Bridge

The bridge enables bidirectional communication between ROS and Ethereum:

```bash
cd dao-bridge/ros-eth-bridge/docker
docker compose up -d

# Verify bridge is running
docker logs ros-eth-bridge --tail 30
```

**Expected output**:
```
[INFO] dao_listener ready — chain 1337
[INFO] dao_writer ready — chain 1337 sender 0x...
[INFO] dao_writer running
```

**Reference**: [dao-bridge/ros-eth-bridge/docker/README.md](dao-bridge/ros-eth-bridge/docker/README.md)

### Step 6: Start Web Console

The web console provides a user interface for task and service management:

```bash
cd dao-bridge/org-web
docker compose up -d

# Verify web console is running
docker logs rodeo-org-web --tail 20
```

Access the console at: **http://localhost:8080**

**Expected output**:
```
✅ Configuration loaded via environment variables
Connected: True
```

**Reference**: [dao-bridge/org-web/README.md](dao-bridge/org-web/README.md)

### Step 7: Run Integration Demo

Execute the full workflow demonstration using Docker:

```bash
cd quick-start/docker

# First time (or after modifying the script):
./robot-emulator.sh build

# Start the emulator:
./robot-emulator.sh start

# Follow the logs:
./robot-emulator.sh logs
```

On subsequent runs (service already registered on-chain), skip registration:

```bash
# Edit docker-compose.yml and uncomment the --skip-registration command override,
# or stop the container and run with the flag directly:
docker run --rm --network host \
  -v $(pwd)/../oracle/proofs:/root/oracle/proofs:ro \
  robot-emulator-demo \
  python3 /root/robot_emulator_ws/robot_emulator_demo.py --skip-registration
```

**The demo will**:
1. Register a delivery service on the blockchain (check the web UI and you will see a new service being created)
2. Use the organizaation web console to create a new task!

   2.1 Navigate to the Tasks tab and create a new task with the following info:
   - Title: Package delivery
   - Description: Package delivery
   - Category: Logistics
   - Task Type: ItemTransport
   - Reward: 100
     
   2.2 After creating the task on the web console you will notice that the task has been assigned to the robot wallet 
4. On the robot emulator terminal you will notice that the robot recives the task assigment and starts the task execution.
5. After task completition the robot submit a rosbag proof of completion
6. On the oracle terminal you can notice that new proof has been recived and is being validated. This can take some time since the oracle is replaying the rosbag and validating different steps. In the end you will see a screen that says:
```
rodeo-oracle  | Validation summary
rodeo-oracle  |   Base path: OK  total 10.956 m, min 0.100 m
rodeo-oracle  |   Arm: OK  net delta 13.4467 rad, tol 0.0500 rad, moves 952
rodeo-oracle  |   Arm top joints by change: shoulder:3.069, wrist_rotate:3.037, forearm_roll:3.036
rodeo-oracle  |   Disposal event: OK  correct flag seen True
rodeo-oracle  | APPROVED
rodeo-oracle  |
rodeo-oracle  | ----- validator output end -----
rodeo-oracle  |
rodeo-oracle  | Approved task 1
rodeo-oracle  |
rodeo-oracle  | Task 1 verified
```
7. Next check the web console, in the home tab you can see that the payment is released to the robot.

**Expected output**:
```
==============================================================
RODEO Robot Emulator - Full Integration Demo
==============================================================
✅ Action servers connected!

📝 Step 1: Registering delivery service...
✅ Service registered successfully!

🎯 Step 2: TASK ASSIGNED!
   Task ID: 1
   Reward: 100.0 IEC

🤖 Step 3: Executing task...
✅ Task execution completed!

📤 Step 4: Submitting proof of completion...
✅ Proof submitted successfully!

⏳ Step 5: Waiting for oracle validation...
✅ Task verified by oracle!
💰 Payment received!
```

Monitor the oracle logs to see the validation process:

```bash
docker logs -f rodeo-oracle
```

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Disk**: 20 GB free space
- **OS**: Ubuntu 20.04+ (or compatible Linux distribution)
- **Docker**: 20.10+
- **Docker Compose**: V2 (use `docker compose`, not `docker-compose`)

### Recommended Requirements
- **CPU**: 8+ cores
- **RAM**: 16 GB
- **Disk**: 50 GB free space (SSD recommended)
- **Network**: Stable internet connection for Docker image downloads


<!--
## Citation

If you use RODEO in your research, please cite:

```bibtex
@article{rodeo2026,
  title={RODEO: A Blockchain-Based Framework for Decentralized Robot Coordination},
  author={[Your Name]},
  journal={[Journal Name]},
  year={2026},
  note={Scientific artifact available at: [Repository URL]}
}
```
-->
## License

[Specify License - e.g., MIT, Apache 2.0, GPL-3.0]

## Contributing

This is a scientific artifact. For questions or collaboration inquiries, please contact milan.groshev(at)ie(dot)edu.

## Acknowledgments

This work was supported by project PID2023-152334OA-I00, funded by MCIU/AEI/10.13039/501100011033 and by FEDER, EU. It was also supported by the Ramón y Cajal fellowship RYC2023-043120-I, funded by MCIU/AEI/10.13039/501100011033 and by FSE+. Additional funding was provided by the 2024 Leonardo Grant for Scientific Research and Cultural Creation (LEO24-1-12086-CCD-CIA-1) from the BBVA Foundation. The BBVA Foundation accepts no responsibility for the opinions, statements and contents included in this publication, which are entirely the responsibility of the authors.

---

**Scientific Artifact Version**: 1.0  
**Last Updated**: March 2026  
**Status**: Research Prototype
