# Robot Emulator Quick Start

Run the robot emulator demo in Docker with three simple commands.

## Prerequisites

Ensure these are running first:

```bash
# 1. Start Ganache blockchain
cd blockchain-network/ganache-docker
./ganache-docker.sh start

# 2. Deploy smart contracts
cd blockchain-network/smart-contracts/docker
./deploy.sh

# 3. Start ROS-ETH Bridge
cd dao-bridge/ros-eth-bridge/docker
./ros-bridge.sh start
```

## Run the Robot Emulator

### 1. Build
```bash
cd quick-start/docker
./robot-emulator.sh build
```

### 2. Start
```bash
./robot-emulator.sh start
```

### 3. Monitor
```bash
./robot-emulator.sh logs
```

## What Happens

The robot emulator will:

1. **Register Service** (auto)
   - Service type: `delivery`
   - Hourly rate: 50 tokens

2. **Wait for Task** (listens to `/dao/task_assigned`)
   - Subscribe to task assignments
   - Receive task from organization

3. **Execute Task** (simulated)
   - 5-second simulation
   - Progress messages

4. **Submit Proof** (auto)
   - Upload ROS bag file
   - Oracle validates
   - Payment processed

## Expected Output

```
[INFO] Robot Delivery Service starting...
[INFO] Waiting for action servers...
[INFO] Step 1: Registering service...
[INFO]    ✅ Service registered successfully!
[INFO] Step 2: Waiting for task assignments...
[INFO] Step 3: Executing task: Deliver package
[INFO]    ⏳ Task in progress...
[INFO]    ✅ Task completed!
[INFO] Step 4: Submitting proof of completion...
[INFO]    ✅ Proof file verified
[INFO]    ✅ Proof submitted successfully!
```

## Control Commands

```bash
./robot-emulator.sh start    # Start robot
./robot-emulator.sh stop     # Stop robot
./robot-emulator.sh restart  # Restart
./robot-emulator.sh logs     # View logs
./robot-emulator.sh status   # Check status
```

## Full Demo Workflow

To test the complete system:

1. **Create Organization**:
   ```bash
   rostopic pub -1 /dao/create_organization ros_eth_msgs/CreateOrganization \
     "org_name: 'Delivery Co'
      org_description: 'Package delivery'
      token_name: 'DeliveryCoin'
      token_symbol: 'DLVR'"
   ```

2. **Post Task**:
   ```bash
   rostopic pub -1 /dao/post_task ros_eth_msgs/PostTask \
     "task_description: 'Deliver package to Building A'
      reward: 100
      required_service: 'delivery'"
   ```

3. **Watch Robot Execute** (logs will show all steps)

4. **Verify on Blockchain** (check wallet balance changed)

## Troubleshooting

**Robot exits immediately**:
```bash
# Check ROS master
rostopic list

# Check bridge status
cd ../../dao-bridge/ros-eth-bridge/docker
./ros-bridge.sh status
```

**Cannot find action servers**:
```bash
# Restart ROS-ETH bridge
cd ../../dao-bridge/ros-eth-bridge/docker
./ros-bridge.sh restart
```

**Proof file not found**:
```bash
# Verify proof exists
ls -lh ../../oracle/proofs/task_tid10_20250910_145742.bag
```

## Next Steps

- See [README.md](README.md) for detailed documentation
- Check [main quick-start README](../README.md) for more examples
- Review [ROS-ETH Bridge docs](../../dao-bridge/ros-eth-bridge/docker/README.md)
