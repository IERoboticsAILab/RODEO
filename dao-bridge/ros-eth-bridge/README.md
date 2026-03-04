# ROS-ETH Bridge

Bidirectional communication layer enabling ROS robots to interact with RODEO blockchain smart contracts. Implements Web3.py integration for task coordination, service registration, and token operations.

## Architecture

**`dao_writer_node`:** Blockchain write operations via ROS action servers  
**`dao_listener_node`:** Continuous event monitoring with ROS topic publishers

Both nodes share a Web3 connection to the Ethereum RPC endpoint, with nonce locking ensuring transaction serialization.

## Features

### Write Operations (Action Servers)
- **Task Management:** Register, activate, remove tasks; submit execution proofs
- **Service Management:** Register, activate, remove services; control availability status
- **Token Operations:** Transfer IECoin, approve spending allowances

### Read Operations (Services)
- **Query Interface:** Retrieve tasks/services by ID or creator address
- **Token Queries:** Check balances and allowances

### Event Publishing (Topics)
Real-time blockchain event stream:
- `TaskRegistered`, `TaskAssigned`, `TaskUnassigned`, `TaskVerified`, `TaskRejected`
- `ServiceRegistered`, `ServiceBusyUpdated`

## Configuration

**`config/dao.yaml`**
```yaml
chain:
  rpc_url: ws://127.0.0.1:8545
  chain_id: 1337
contracts:
  iecoin: "0x..."
  organization: "0x..."
  task_manager: "0x..."
  service_manager: "0x..."
wallet:
  keystore_path: ~/.ros_eth/wallet.json
  address: "0x..."
transaction:
  confirmations: 1
  gas_limit: 3000000
```

## Quick Start

### Docker Deployment (Recommended)

**Prerequisites:** Docker, Docker Compose, ROS Master running, Ganache running

```bash
cd docker

# 1. Configure contracts
nano configs/dao.yaml  # Update contract addresses

# 2. Setup wallet
mkdir -p ~/.ros_eth
python3 configs/make_wallet.py

# 3. Build and start
./ros-eth-bridge-docker.sh build
./ros-eth-bridge-docker.sh start

# 4. Verify
./ros-eth-bridge-docker.sh logs
```

📖 **See [docker/QUICKSTART.md](docker/QUICKSTART.md) for detailed Docker deployment guide**  
📖 **See [docker/README.md](docker/README.md) for Docker configuration and troubleshooting**

### Native ROS Build

For native ROS Noetic development and deployment without Docker:

📖 **See [catkin_ws/README.md](catkin_ws/README.md) for native ROS Noetic build instructions**

Quick native start:
```bash
cd catkin_ws
catkin_make && source devel/setup.bash
roslaunch ros_eth_bridge ros_eth_gateway.launch
```

## ROS API

### Action Servers

| Action | Description |
|--------|-------------|
| `/dao/register_task_action` | Register new task with reward |
| `/dao/activate_task_action` | Enable task for assignment |
| `/dao/remove_task_action` | Delete task from registry |
| `/dao/submit_proof_action` | Submit task completion proof |
| `/dao/register_service_action` | Register robot service |
| `/dao/activate_service_action` | Enable service availability |
| `/dao/remove_service_action` | Delete service from registry |
| `/dao/set_service_busy_action` | Update service busy status |
| `/dao/transfer_token_action` | Transfer IECoin tokens |
| `/dao/approve_spender_action` | Approve token spending |

### Services

| Service | Description |
|---------|-------------|
| `/dao/get_task_by_id` | Retrieve task details |
| `/dao/get_all_tasks` | List all tasks |
| `/dao/get_tasks_by_creator` | Filter tasks by creator |
| `/dao/get_service_by_id` | Retrieve service details |
| `/dao/get_all_services` | List all services |
| `/dao/get_services_by_creator` | Filter services by creator |
| `/dao/get_balance` | Query IECoin balance |
| `/dao/get_allowance` | Query token allowance |

### Topics (Published)

| Topic | Type | Description |
|-------|------|-------------|
| `/dao/task_registered` | `TaskRegistered` | New task created |
| `/dao/task_assigned` | `TaskAssignment` | Task assigned to executor |
| `/dao/task_unassigned` | `TaskId` | Task assignment cancelled |
| `/dao/task_verified` | `TaskId` | Task completion verified |
| `/dao/task_rejected` | `TaskRejection` | Task proof rejected |
| `/dao/service_registered` | `ServiceMeta` | New service registered |
| `/dao/service_busy` | `ServiceBusy` | Service availability changed |

## Usage Examples

**Register task:**
```bash
rostopic pub -1 /dao/register_task_action/goal ros_eth_msgs/RegisterTaskActionGoal \
  '{goal: {description: "Battery charging", category: "Power", task_type: "BatteryCharging", reward: "50", min_confirmations: 1}}'
```

**Query all tasks:**
```bash
rosservice call /dao/get_all_tasks
```

**Monitor task events:**
```bash
rostopic echo /dao/task_assigned
```

See [tests/integration_test.py](tests/integration_test.py) for comprehensive examples.

