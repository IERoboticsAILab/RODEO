# Quick Start

Demo scenarios and tutorials for the RODEO (Robotic Decentralized Organization) system.

---

## 🤖 Robot Emulator Demo

[robot_emulator_demo.py](robot_emulator_demo.py) is the main integration demo script. It simulates a robot that participates in the full RODEO lifecycle end-to-end, without needing a real physical robot:

```
[Register service] → [Receive task] → [Execute task] → [Submit proof] → [Receive reward]
```

### What it does, step by step

| Step | What happens |
|------|-------------|
| 1 | Connects to the ROS-ETH bridge action servers |
| 2 | Registers a **Delivery Service** on the blockchain (`RegisterServiceAction`) |
| 3 | Subscribes to `/dao/task_assigned` — waits for a task to be posted and assigned |
| 4 | Simulates task execution (10-second countdown) |
| 5 | Submits a ROS bag file as proof of completion (`SubmitProofAction`) |
| 6 | Subscribes to `/dao/task_verified` — prints a success banner when the oracle validates the proof and the reward is paid |

---

## 🐳 Running with Docker (recommended)

Docker is the easiest way to run the emulator — no ROS installation needed on the host.

### Prerequisites

All services must be running before starting the emulator:

| Service | Directory | Start command |
|---------|-----------|---------------|
| Ganache blockchain | `blockchain-network/ganache-docker/` | `./ganache-docker.sh start` |
| Smart contracts deployed | `blockchain-network/smart-contracts/` | `./deploy.sh` |
| ROS-ETH bridge | `dao-bridge/ros-eth-bridge/docker/` | `./ros-bridge.sh start` |
| Oracle | `oracle/docker/` | `docker compose up -d` |
| Web console | `dao-bridge/org-web/` | `./org-web-docker.sh start` |

### Build and start

```bash
cd quick-start/docker

# First time (or after modifying the script):
./robot-emulator.sh build

# Start the emulator:
./robot-emulator.sh start

# Follow the logs:
./robot-emulator.sh logs
```

### Skip registration on subsequent runs

The service only needs to be registered once per Ganache session. On subsequent runs, pass `--skip-registration` to avoid a duplicate-registration error:

```bash
# Edit docker-compose.yml and uncomment the command override, or run directly:
docker run --rm --network host \
  -v $(pwd)/../../oracle/proofs:/root/oracle/proofs:ro \
  robot-emulator-demo \
  python3 /root/robot_emulator_ws/robot_emulator_demo.py --skip-registration
```

Or edit [docker/docker-compose.yml](docker/docker-compose.yml) and uncomment the `command:` line.

### All control script commands

```bash
./robot-emulator.sh build      # Build Docker image
./robot-emulator.sh start      # Start container (detached)
./robot-emulator.sh stop       # Stop container
./robot-emulator.sh restart    # Rebuild + restart
./robot-emulator.sh logs       # Follow container logs
./robot-emulator.sh status     # Check if running
./robot-emulator.sh shell      # Interactive bash inside container
./robot-emulator.sh help       # Show help
```

---

## 🐍 Running natively (without Docker)

If you have ROS Noetic and the workspace already sourced:

```bash
# Source the ros_eth_msgs workspace
source dao-bridge/ros-eth-bridge/catkin_ws/devel/setup.bash

# Run with service registration (first run):
python3 quick-start/robot_emulator_demo.py

# Run skipping registration (subsequent runs):
python3 quick-start/robot_emulator_demo.py --skip-registration
```

### `--skip-registration` flag

| Scenario | Command |
|----------|---------|
| First run, or after a blockchain reset | `python3 robot_emulator_demo.py` |
| Subsequent runs on same Ganache session | `python3 robot_emulator_demo.py --skip-registration` |

When `--skip-registration` is used the script skips Step 2 entirely and goes straight to listening for task assignments. Use this when the service is already registered on-chain to avoid a transaction revert.

---

## 🔄 Full demo workflow

Once the emulator is running and listening, trigger the workflow from the web console or via ROS topics:

### Option A — Web console

1. Open **http://localhost:8080**
2. Navigate to **Tasks**
3. Click **Register New Task** and fill in:
   - Description: `Package delivery`
   - Category: `Logistics`
   - Task Type: `ItemTransport`
   - Reward: `100 IEC`
4. Submit — the robot takes it from here automatically

### Option B — ROS topics

```bash
# Post a task directly
rostopic pub -1 /dao/post_task ros_eth_msgs/PostTask \
  "task_description: 'Deliver package to Building A'
   reward: 100
   required_service: 'ItemTransport'"
```

### Expected console output

```
✅ Service registered! TX: 0xabc...  Block: 42
✅ Robot ready - listening for task assignments

🎯 Task assigned! ID: 1  Reward: 100.0 IEC
🤖 Step 3: Executing task (10 seconds simulation)...
   ⏱  10s remaining...  ...  ⏱  1s remaining...
✅ Task execution completed!

📤 Step 4: Submitting proof of completion...
✅ Proof submitted! TX: 0xdef...  Block: 47
🔍 Step 5: Waiting for oracle validation...

════════════════════════════════════════════════════════════
🏆 Task 1 verified — reward received!
   Oracle validated the proof successfully.
   Demo complete! ✅
════════════════════════════════════════════════════════════
```

---

## 📚 Other demo scripts

**[demo.py](demo.py)** — Navigation demo with Stage simulator  
Delivery, battery charging, and cleaning task scenarios using `move_base`.

**[demo_with_eth_interface.py](demo_with_eth_interface.py)** — Blockchain-integrated navigation  
Combines Stage navigation with live blockchain transactions.

**[navigation_move_base.py](navigation_move_base.py)** — Navigation helper module  
Wraps the `move_base` action server; used by the demos above.

**[simulator/](simulator/)** — Stage simulator environment  
ROS Stage map and configuration for navigation testing.

---

## 📖 Tutorials

**[TUTORIAL_FULL_DEMO.md](TUTORIAL_FULL_DEMO.md)** — Complete end-to-end walkthrough  
Covers Ganache setup, contract deployment, bridge config, oracle setup, web console, and the full task workflow.

**[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Fast reference card  
Quick commands and config templates for experienced users.

---

## Create Organization and Post Task

Use ROS topics to interact:

```bash
# Create organization
rostopic pub -1 /dao/create_organization ros_eth_msgs/CreateOrganization \
  "org_name: 'Delivery Co'
   org_description: 'Package delivery service'
   token_name: 'DeliveryCoin'
   token_symbol: 'DLVR'"

# Post task
rostopic pub -1 /dao/post_task ros_eth_msgs/PostTask \
  "task_description: 'Deliver package to Building A'
   reward: 100
   required_service: 'delivery'"
```

The robot will automatically execute the task and submit proof!

### Alternative: Quick Start with Native Python

If you prefer running without Docker:

```bash
# Prerequisites: ROS Noetic, ros_eth_msgs built
cd quick-start
python3 robot_emulator_demo.py
```

**See Also:**
- [Docker Robot Emulator Guide](docker/README.md) - Detailed Docker setup
- [Docker Quick Start](docker/QUICKSTART.md) - Fast Docker commands
- [Full Tutorial](TUTORIAL_FULL_DEMO.md) - Complete walkthrough

## Navigation Scenarios

### Delivery Task
```python
app = DemoMissionNode()
app.run_task_delivery()
# Robot: start_room → bottom_right → start_room
```

### Battery Charging
```python
app.run_task_battery_charging()
# Robot: current_position → top_left (charging station)
```

### Cleaning Task
```python
app.run_task_cleaning()
# Robot: patrols all rooms in sequence
```

## Map Waypoints

Available navigation points in Stage simulator:

| Location | Coordinates (x, y) | Description |
|----------|-------------------|-------------|
| `start_room` | (-13.045, 4.102) | Initial spawn location |
| `bottom_right` | (-18.698, -11.069) | Delivery destination |
| `front_start` | (2.303, 8.280) | Corridor entrance |
| `top_left` | (19.112, 18.273) | Charging station |
| `top_right` | (19.155, -16.322) | Storage room |
| `big_room` | (12.638, -6.038) | Main workspace |
| `hallway` | (-11.009, -10.938) | Transit corridor |

## Requirements

### For Navigation Demos
- ROS Noetic
- Stage simulator
- move_base navigation stack

### For Blockchain Integration
- Ganache (local blockchain)
- Smart contracts deployed
- ROS-ETH bridge
- Oracle node
- Web console

## Next Steps

1. **Run integration demo** - Follow [TUTORIAL_FULL_DEMO.md](TUTORIAL_FULL_DEMO.md)
2. **Customize scenarios** - Modify [demo.py](demo.py) waypoints
3. **Add new tasks** - Extend robot_emulator_demo.py
4. **Deploy to testnet** - Configure for Sepolia/Mumbai

## Documentation

- **Blockchain Network:** [../blockchain-network/README.md](../blockchain-network/README.md)
- **Smart Contracts:** [../blockchain-network/smart-contracts/README.md](../blockchain-network/smart-contracts/README.md)
- **DAO Bridge:** [../dao-bridge/README.md](../dao-bridge/README.md)
- **ROS Bridge:** [../dao-bridge/ros-eth-bridge/README.md](../dao-bridge/ros-eth-bridge/README.md)
- **Web Console:** [../dao-bridge/org-web/README.md](../dao-bridge/org-web/README.md)

