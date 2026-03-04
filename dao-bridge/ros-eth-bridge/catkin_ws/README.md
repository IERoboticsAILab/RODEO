# ROS-ETH Bridge - Native ROS Noetic Build

This directory contains the Catkin workspace for building and running the ROS-ETH Bridge natively with ROS Noetic.

## Overview

The native build allows direct development and debugging of the ROS-ETH Bridge nodes without Docker. This is useful for:
- Active ROS package development
- Debugging with IDE integration
- Custom ROS workspace integration
- Testing on physical robots with native ROS

**For production deployment or quick start, use Docker instead:** See [../docker/README.md](../docker/README.md)

---

## Prerequisites

### System Requirements
- **Ubuntu 20.04** (Focal Fossa)
- **ROS Noetic** Desktop-Full installation
- **Python 3.8+**
- **Git**

### Install ROS Noetic

If not already installed:

```bash
# Setup sources
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

# Install ROS Noetic
sudo apt update
sudo apt install ros-noetic-desktop-full

# Setup environment
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

# Install build tools
sudo apt install python3-rosdep python3-rosinstall python3-rosinstall-generator python3-wstool build-essential

# Initialize rosdep
sudo rosdep init
rosdep update
```

### Install Python Dependencies

```bash
# Install web3.py and dependencies
pip3 install web3 pyyaml eth-account
```

---

## Building the Workspace

### 1. Navigate to Workspace

```bash
cd dao-bridge/ros-eth-bridge/catkin_ws
```

### 2. Install ROS Dependencies

```bash
# Install any missing ROS packages
rosdep install --from-paths src --ignore-src -r -y
```

### 3. Build with Catkin

```bash
# Clean build (recommended first time)
catkin_make clean
catkin_make

# Or build in release mode for better performance
catkin_make -DCMAKE_BUILD_TYPE=Release
```

Expected output:
```
####
#### Running command: "make -j8 -l8" in "/path/to/catkin_ws/build"
####
[ 50%] Building CXX object ...
[100%] Linking CXX executable ...
[100%] Built target ros_eth_bridge_node
```

### 4. Source the Workspace

```bash
source devel/setup.bash
```

**Make it permanent:**
```bash
echo "source ~/dao-bridge/ros-eth-bridge/catkin_ws/devel/setup.bash" >> ~/.bashrc
```

---

## Configuration

### 1. Update Contract Addresses

Edit the configuration file:

```bash
nano src/ros_eth_bridge/config/dao.yaml
```

Update with your deployed contract addresses:

```yaml
contracts:
  iecoin: "0x1613beB3B2C4f22Ee086B2b38C1476A3cE7f78E8"
  organization: "0x1C674bf0d074Dc54bb13D1e6291C0cE88054C5b5"
  task_manager: "0x49A1cc3dDE359E254c48808E4bD83e331A3cC311"
  service_manager: "0x12aEdb6639C160B051be89B77717F46eafac282b"

wallet:
  keystore_path: ~/.ros_eth/wallet.json
  address: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

chain:
  rpc_url: ws://127.0.0.1:8545
  http_fallback_url: http://127.0.0.1:8545
  chain_id: 1337
```

Get addresses from:
```bash
cat ../../../../blockchain-network/smart-contracts/deployments/1337.json
```

### 2. Setup Wallet

Create wallet keystore:

```bash
mkdir -p ~/.ros_eth
python3 ../docker/configs/make_wallet.py
# Enter passphrase when prompted
```

Or copy existing wallet:
```bash
cp /path/to/wallet.json ~/.ros_eth/wallet.json
```

---

## Running the Bridge

### Start ROS Master

In a separate terminal:
```bash
roscore
```

### Launch the Bridge

```bash
source devel/setup.bash
roslaunch ros_eth_bridge ros_eth_gateway.launch
```

**With custom config:**
```bash
roslaunch ros_eth_bridge ros_eth_gateway.launch config:=/path/to/custom/dao.yaml
```

**Expected output:**
```
NODES
dao_listener (ros_eth_bridge/dao_listener_node.py)
dao_writer (ros_eth_bridge/dao_writer_node.py)
ROS_MASTER_URI=http://localhost:11311
ros-eth-bridge
process[dao_listener-1]: started with pid [70]
process[dao_writer-2]: started with pid [71]
[INFO]: dao_listener ready — chain 1337
[INFO]: dao_writer ready — chain 1337  sender 0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65
[INFO]: dao_writer running
```

---

## Verification

### Check ROS Nodes

```bash
rosnode list
```

Expected:
```
/dao_listener_node
/dao_writer_node
/rosout
```

### Check ROS Topics

```bash
rostopic list
```

Expected:
```
/dao/task_registered
/dao/task_assigned
/dao/task_verified
/dao/service_registered
...
```

### Check Action Servers

```bash
rostopic list | grep /dao/.*_action
```

Expected:
```
/dao/register_task_action/cancel
/dao/register_task_action/feedback
/dao/register_task_action/goal
/dao/register_task_action/result
/dao/register_task_action/status
...
```

---

## Package Structure

```
catkin_ws/
├── src/
│   └── ros_eth_bridge/
│       ├── config/
│       │   └── dao.yaml              # Configuration file
│       ├── launch/
│       │   └── ros_eth_gateway.launch # Launch file
│       ├── scripts/
│       │   ├── dao_writer_node.py    # Write operations
│       │   └── dao_listener_node.py  # Event listening
│       ├── msg/                      # Custom message types
│       ├── action/                   # Action definitions
│       └── srv/                      # Service definitions
├── devel/                            # (Generated) Build outputs
└── build/                            # (Generated) Build artifacts
```

---

## See Also

- **Docker Deployment:** [../docker/README.md](../docker/README.md) - Recommended for production
- **Main ROS-ETH Bridge:** [../README.md](../README.md) - Architecture and API documentation
- **Quick Start:** [../docker/QUICKSTART.md](../docker/QUICKSTART.md) - Fast Docker setup

---

## License

MIT License
