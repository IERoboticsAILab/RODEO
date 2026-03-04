# Robot Emulator Docker Deployment

Docker container for running the robot emulator demo that simulates a robot interacting with the RODEO (Robotic Decentralized Organization) system.

## Overview

The robot emulator demonstrates:
- **Service Registration**: Registers a delivery service with capabilities
- **Task Assignment**: Listens for task assignments from the organization
- **Task Execution**: Simulates task execution with timing
- **Proof Submission**: Submits proof files (ROS bag) to verify task completion

## Prerequisites

1. **Ganache blockchain** running on port 8545
2. **ROS Master** (roscore) running on port 11311
3. **ROS-ETH Bridge** running with action servers
4. **Smart Contracts** deployed
5. **Organization** created with task posted

## Quick Start

### 1. Build the Container

```bash
cd quick-start/docker
./robot-emulator.sh build
```

### 2. Start the Robot Emulator

```bash
./robot-emulator.sh start
```

The robot will:
1. Register a delivery service
2. Wait for task assignments on `/dao/task_assigned` topic
3. Simulate task execution (5 seconds)
4. Submit proof automatically

### 3. View Logs

```bash
./robot-emulator.sh logs
```

### 4. Stop the Emulator

```bash
./robot-emulator.sh stop
```

## Architecture

```
┌─────────────────────────┐
│  Robot Emulator         │
│  (Docker Container)     │
│                         │
│  ┌──────────────────┐  │
│  │ robot_emulator_  │  │
│  │ demo.py          │  │
│  │                  │  │
│  │ - ActionClient   │  │
│  │ - Topic Sub      │  │
│  └──────────────────┘  │
└────────┬────────────────┘
         │ ROS Topics/Actions
         │ (network_mode: host)
         ▼
┌─────────────────────────┐
│  ROS-ETH Bridge         │
│  - /dao/register_service│
│  - /dao/submit_proof    │
│  - /dao/task_assigned   │
└────────┬────────────────┘
         │ Web3.py
         ▼
┌─────────────────────────┐
│  Smart Contracts        │
│  - ServiceManager       │
│  - TaskManager          │
└─────────────────────────┘
```

## Configuration

### Proof Files

The container mounts the proof files directory as read-only:

```yaml
volumes:
  - ../../oracle/proofs:/root/oracle/proofs:ro
```

The emulator uses:
- **Proof File**: `task_tid10_20250910_145742.bag`
- **Location in container**: `/root/oracle/proofs/`
- The path matches the script's relative path calculation

### ROS Environment

The container uses `network_mode: host` to access:
- **ROS Master**: `http://localhost:11311`
- **ROS Topics/Actions**: Available on host network

### Custom Messages

The container mounts the ROS-ETH bridge workspace to access custom message definitions:

```yaml
volumes:
  - ../../dao-bridge/ros-eth-bridge/docker/catkin_ws:/root/catkin_ws:ro
```

This provides access to `ros_eth_msgs` package:
- `RegisterServiceAction`
- `SubmitProofAction`
- `TaskAssignment`

## Control Script Commands

```bash
./robot-emulator.sh build      # Build Docker image
./robot-emulator.sh start      # Start container
./robot-emulator.sh stop       # Stop container
./robot-emulator.sh restart    # Restart container
./robot-emulator.sh logs       # View logs (follow mode)
./robot-emulator.sh status     # Check if running
./robot-emulator.sh shell      # Interactive shell
./robot-emulator.sh help       # Show help
```

## Workflow Example

### Complete Demo Flow

1. **Start all required services**:
   ```bash
   # Terminal 1: Start Ganache
   cd blockchain-network/ganache-docker
   ./ganache-docker.sh start
   
   # Terminal 2: Deploy contracts
   cd blockchain-network/smart-contracts/docker
   ./deploy.sh
   
   # Terminal 3: Start ROS-ETH Bridge
   cd dao-bridge/ros-eth-bridge/docker
   ./ros-bridge.sh start
   ```

2. **Create organization and post task**:
   ```bash
   # Create organization
   rostopic pub -1 /dao/create_organization ros_eth_msgs/CreateOrganization \
     "org_name: 'Delivery Co'
      org_description: 'Package delivery service'
      token_name: 'DeliveryCoin'
      token_symbol: 'DLVR'"
   
   # Post task
   rostopic pub -1 /dao/post_task ros_eth_msgs/PostTask \
     "task_description: 'Deliver package'
      reward: 100
      required_service: 'delivery'"
   ```

3. **Start robot emulator**:
   ```bash
   cd quick-start/docker
   ./robot-emulator.sh start
   ./robot-emulator.sh logs
   ```

4. **Watch the robot**:
   - Register delivery service
   - Receive task assignment
   - Execute task (5s simulation)
   - Submit proof file
   - Oracle validates proof
   - Payment processed

## Troubleshooting

### Container Won't Start

**Issue**: Container exits immediately

**Solutions**:
```bash
# Check if ROS master is running
rostopic list

# Check logs for errors
./robot-emulator.sh logs

# Verify ROS-ETH bridge is running
rosservice list
```

### Cannot Connect to Action Servers

**Issue**: Action servers not available

**Solutions**:
```bash
# Verify ROS-ETH bridge is running
cd ../../dao-bridge/ros-eth-bridge/docker
./ros-bridge.sh status

# Check action servers
rostopic list | grep -E 'register_service|submit_proof'
```

### Proof File Not Found

**Issue**: Cannot find proof file in container

**Solutions**:
```bash
# Verify proof file exists
ls -lh ../../oracle/proofs/task_tid10_20250910_145742.bag

# Check volume mount
docker inspect robot-emulator-demo | grep -A 5 Mounts
```

### Custom Messages Not Found

**Issue**: `ros_eth_msgs` not available

**Solutions**:
```bash
# Verify ros-eth-bridge workspace exists
ls -la ../../dao-bridge/ros-eth-bridge/docker/catkin_ws/devel/

# Rebuild ROS-ETH bridge
cd ../../dao-bridge/ros-eth-bridge/docker
./ros-bridge.sh build
```

## Development

### Running Without Docker

If you need to modify the script frequently:

```bash
# Install dependencies
sudo apt-get install ros-noetic-actionlib python3-rospy python3-actionlib

# Build ros_eth_msgs
cd ../dao-bridge/ros-eth-bridge/catkin_ws
catkin_make
source devel/setup.bash

# Run directly
cd quick-start
python3 robot_emulator_demo.py
```

### Modifying the Emulator

The robot emulator script is copied into the image at build time. After modifications:

```bash
./robot-emulator.sh stop
./robot-emulator.sh build
./robot-emulator.sh start
```

## Network Architecture

The container uses `network_mode: host` to:
- Access ROS master without complex networking
- Communicate with ROS topics/actions seamlessly
- Connect to localhost services (Ganache, bridge)

This means:
- ✅ No port mapping needed
- ✅ Direct ROS communication
- ✅ Simple configuration
- ⚠️ Container shares host network namespace

## See Also

- [Quick Start Main README](../README.md) - Full demo documentation
- [ROS-ETH Bridge Docker](../../dao-bridge/ros-eth-bridge/docker/README.md) - Bridge deployment
- [Smart Contracts Docker](../../blockchain-network/smart-contracts/docker/README.md) - Contract deployment
- [Oracle README](../../oracle/README.md) - Proof validation
