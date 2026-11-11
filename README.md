<h1 align="center">
RODEO: Robotic Decentralized Organization
</h1>





<p align="center">
<a href="https://rodeo.cyphy.life/">
<img src="https://img.shields.io/badge/Web%20Page-blue?style=flat&logo=google-chrome&logoColor=white">
</a>

<a href="https://arxiv.org/abs/2603.06058">
<img src="https://img.shields.io/badge/Paper-arXiv%202603.06058-8b1e3f?style=flat&logo=arxiv&logoColor=white">
</a>

<a href="https://youtu.be/L5voOWKFLzk?si=cIMpkU0fx8_hpq45">
<img src="https://img.shields.io/badge/Demo-Video-cc0000?style=flat&logo=youtube&logoColor=white">
</a>

<a href="./LICENSE.md">
<img src="https://img.shields.io/badge/Code%20License-MIT-6a994e?style=flat">
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
│   ├── ros2-eth-bridge/       # Bidirectional ROS 2 - Ethereum communication
│   └── org-web/               # Web console for DAO management
│
├── robot-agent/               # RODEO robot standard and the robot agent
│
├── oracle/                    # Task verification oracle
│
├── quick-start/               # Demo without a robot: agent + fake executor
│
└── scripts/                   # update-addresses.sh
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

The chain is stored in `blockchain-network/ganache-docker/ganache_db/` (not
committed). To start again from an empty chain: `docker compose down && sudo rm -rf ganache_db`.

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

**Expected output** on a fresh chain (the addresses are deterministic, and are
the ones already in the committed configs):
```
IECoin:          0x5FbDB2315678afecb367f032d93F642f64180aa3
Organization:    0x8464135c8F25Da09e49BC8782676a84730C318bC
ServiceManager:  0x71C95911E9a5D330f4D621842EC243EE1343292e
TaskManager:     0x712516e61C8B383dF4A63CFe83d7701Bce54B03e
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

**Reference**: See [dao-bridge/ros2-eth-bridge/README.md](dao-bridge/ros2-eth-bridge/README.md) for details.

### Step 4: Start Oracle Node

The oracle validates task completion proofs. It runs as ROS 2 nodes (the oracle
plus one validator node per service type); a pure-Python oracle with the same
checks is also available (`--profile python`, see [oracle/README.md](oracle/README.md)):

```bash
cd oracle/docker
docker compose up -d --build

# Verify oracle is running
docker logs rodeo-oracle --tail 20
```

**Expected output**:
```
[delivery_validator]: delivery validator ready (Logistics/ItemTransport)
✅ Oracle configuration loaded from environment variables
[oracle]: validator Logistics/ItemTransport -> /oracle/validate/delivery
Starting event watcher from block 0 (current: X)
Watching oracle requests and outcomes
```

**Reference**: [oracle/docker/README.md](oracle/docker/README.md)

### Step 5: Start ROS-Ethereum Bridge

The bridge (ROS 2 Humble) enables bidirectional communication between ROS and Ethereum.
It signs with the robot's keystore, which you create once:

```bash
cd dao-bridge/ros2-eth-bridge
pip3 install eth-account
python3 scripts/make_wallet.py        # press Enter for an empty dev passphrase

cd docker
docker compose up -d --build

# Verify bridge is running
docker logs ros2-eth-bridge --tail 30
```

**Expected output**:
```
[dao_listener]: dao_listener ready - chain 1337 ... assignments for 0x15d34AAf... only
[dao_writer]: dao_writer ready - chain 1337  sender 0x15d34AAf...
```

**Reference**: [dao-bridge/ros2-eth-bridge/README.md](dao-bridge/ros2-eth-bridge/README.md)

### Step 6: Start Web Console

The web console provides a user interface for task and service management:

```bash
cd dao-bridge/org-web
docker compose up -d

# Verify web console is running
docker logs org-web-console --tail 20
```

Access the console at: **http://localhost:8080**

**Expected output**:
```
✅ Configuration loaded via environment variables
Connected: True
```

**Reference**: [dao-bridge/org-web/README.md](dao-bridge/org-web/README.md)

### Step 7: Run Integration Demo

Run a robot's RODEO software without a robot: the agent plus a fake executor
that stands in for the robot (see [quick-start/README.md](quick-start/README.md)):

```bash
cd quick-start/docker

# First time (or after code changes):
./demo.sh build

# Start the agent and the fake executor:
./demo.sh start

# Follow the logs:
./demo.sh logs
```

Both use the bridge's `ROS_DOMAIN_ID` (default 40) and namespace (default none).

**The demo will**:
1. Register the Panther's Delivery service on the blockchain (check the web UI and you will see the new service).
2. Use the organization web console to create a new task!

   2.1 Navigate to the Tasks tab, pick **Delivery** in the Service dropdown (only services that are online are listed; Category and Type fill in by themselves), give the task a Title, choose the pick-up and drop-off places under **Delivery details**, and click **Create task**. The reward is pre-filled with the service's price.

   2.2 After creating the task you will notice that it has been assigned to the robot wallet.
3. In the demo logs the agent receives the assignment and the fake executor performs the delivery: pick-up, load, drop-off, unload, recipient confirmation.
4. The agent hashes the proof and submits it.
5. On the oracle terminal you can see the new proof being validated: first the checks every proof must pass (hash, reuse, manifest, parameters, time window), then the delivery validator. In the end you will see:
```
rodeo-oracle  | task 1 validation summary
rodeo-oracle  |   OK    proof hash matches the URI
rodeo-oracle  |   OK    proof not used before
rodeo-oracle  |   OK    manifest task id 1
rodeo-oracle  |   OK    parameters match the task
rodeo-oracle  |   OK    recorded +1.2 s .. +0.2 s relative to assignment/submission (tolerance 5 s)
rodeo-oracle  |   OK    pose at pick-up arrival 0.00 m from 'package_pickup' (max 1.00 m)
rodeo-oracle  |   OK    package loaded at pick-up: 1.200 kg (min 0.05)
rodeo-oracle  |   OK    deck empty after drop-off: 0.000 kg
rodeo-oracle  |   OK    receipt confirmed at 'package_dropoff' by 'the recipient'
rodeo-oracle  | APPROVED
rodeo-oracle  | Approved task 1
rodeo-oracle  | Task 1 verified
```
6. Next check the web console: in the home tab you can see that the payment is released to the robot.
7. Post a second task: the simulated battery then drops below 30 %, and the robot pays the institution's charging station 20 IEC for a charge, verified by the oracle like any other task (see [quick-start/README.md](quick-start/README.md); the station's keystore is created once with `make_wallet.py`).

**Expected output** (abridged):
```
rodeo-demo-agent     | register service 'Delivery' (Logistics/ItemTransport, 100 IEC): ok (block 13)
rodeo-demo-agent     | ready - waiting for assignments
rodeo-demo-agent     | task 1 assigned (reward 100 IEC)
rodeo-demo-agent     | task 1: executing Delivery with {"dropoff": "package_dropoff", "pickup": "package_pickup", ...}
rodeo-demo-executor  | task 1: to_pickup - package_pickup
rodeo-demo-executor  | task 1: waiting_confirm - the recipient takes the package and confirms
rodeo-demo-agent     | task 1: submit proof: ok (block 15)
rodeo-demo-agent     | task 1: VERIFIED - reward paid
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



## Citation

If you use RODEO in your research, please cite:

```bibtex
@INPROCEEDINGS{11696135,
  author={Groshev, Milan and Ferrer, Eduardo Castelló},
  booktitle={2026 IEEE International Conference on Robotics and Automation (ICRA)},
  title={RODEO: RObotic DEcentralized Organization},
  year={2026},
  volume={},
  number={},
  pages={9639-9646},
  keywords={Robots;Organizations;Printing;Decentralized autonomous organization;Timing;Cleaning;IEC;Service robots;Batteries;Bridges},
  doi={10.1109/ICRA57385.2026.11696135}}
}
```

## License

MIT License

## Contributing

This is a scientific artifact. For questions or collaboration inquiries, please contact milan.groshev(at)ie(dot)edu.

## Acknowledgments

This work was supported by project PID2023-152334OA-I00, funded by MCIU/AEI/10.13039/501100011033 and by FEDER, EU. It was also supported by the Ramón y Cajal fellowship RYC2023-043120-I, funded by MCIU/AEI/10.13039/501100011033 and by FSE+. Additional funding was provided by the 2024 Leonardo Grant for Scientific Research and Cultural Creation (LEO24-1-12086-CCD-CIA-1) from the BBVA Foundation. The BBVA Foundation accepts no responsibility for the opinions, statements and contents included in this publication, which are entirely the responsibility of the authors.

---

**Scientific Artifact Version**: 1.0  
**Last Updated**: March 2026  
**Status**: Research Prototype
