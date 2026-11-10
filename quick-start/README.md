# Quick Start: robot emulator

[robot_emulator_demo.py](robot_emulator_demo.py) is a ROS 2 node that plays a
robot through the full RODEO lifecycle without a real robot, using the ROS 2
bridge:

```
[Register service] → [Receive task] → [Execute task] → [Submit proof] → [Receive reward]
```

| Step | What happens |
|------|-------------|
| 1 | Connects to the bridge's action servers |
| 2 | Registers a **Delivery Service** (`dao/register_service_action`) |
| 3 | Waits on `dao/task_assigned` for a task assigned to its wallet |
| 4 | Simulates the task (10-second countdown) |
| 5 | Submits a pre-recorded bag as proof (`dao/submit_proof_action`) |
| 6 | Reports the oracle's verdict (`dao/task_verified` / `dao/task_rejected`) |

It is also the acceptance test for the bridge: a bridge change is good when
this run still ends with the task verified.

## Running with Docker

Prerequisites (see the top-level README): Ganache with the contracts deployed,
org-web, the oracle and the ROS 2 bridge running.

```bash
cd quick-start/docker
./robot-emulator.sh build      # first time, or after changing the script
./robot-emulator.sh start
./robot-emulator.sh logs
```

Then create a task in org-web (`http://localhost:8080`, Tasks tab):

| Field | Value |
|---|---|
| Title | Package delivery |
| Description | Package delivery |
| Category | Logistics |
| Type | ItemTransport |
| Reward | 100 |

Category and Type must match exactly: that is how the contract matches the task
to the service.

| Setting | Default | Notes |
|---|---|---|
| `ROS_DOMAIN_ID` | 40 | must match the bridge |
| `ROBOT_NAMESPACE` | none | must match the bridge, e.g. `panther` |
| `SKIP_REGISTRATION` | false | `SKIP_REGISTRATION=true ./robot-emulator.sh start` when the service is already registered |

The container does not restart on its own, since every start registers another
service. Stop it with `./robot-emulator.sh stop`.

## Running without Docker

```bash
source /opt/ros/humble/setup.bash
source dao-bridge/ros2-eth-bridge/ros2_ws/install/setup.bash   # after colcon build there
PROOF_FILE=$PWD/oracle/proofs/task_tid10_20250910_145742.bag \
  python3 quick-start/robot_emulator_demo.py [--skip-registration] [--ros-args -r __ns:=/panther]
```

The oracle must be able to open the proof path, so outside Docker use a path
the oracle container also mounts (`oracle/proofs` is mounted at
`/root/oracle/proofs`).
