# Oracle Node

The Oracle Node is a trusted verification service that validates task completion proofs submitted by robots and interacts with the blockchain to approve or reject tasks.

## What the Oracle Does

The Oracle serves as an independent verification layer in the RODEO system:

1. **Listens for Proof Submissions** - Monitors `TaskOracleRequested` events when robots submit proofs
2. **Validates Proofs** - Runs shared checks, then the validator registered for the task's service
3. **Makes Decisions** - Approves valid proofs or rejects invalid ones with a specific reason
4. **Updates Blockchain** - Sends `oracleFulfill` to the TaskManager contract
5. **Triggers Payments** - Approved tasks release the escrowed reward to the robot

### Two implementations, one behaviour

| | ROS 2 oracle (default) | Python oracle (alternative) |
|---|---|---|
| Where | `ros2_ws/src/rodeo_oracle`, compose service `oracle` | `oracle_node/`, compose service `oracle-python` (profile `python`) |
| Validators | ROS 2 nodes serving `rodeo_interfaces/srv/ValidateProof`, in any language (C++ or Python), free to use any ROS library | Python functions registered in `oracle_node/validators/` |
| Reads proofs with | `rosbag2` | `rosbags` (no ROS install) |
| Verdicts | logged, and published as JSON on `/oracle/verdicts` | logged |
| Console | none (runs unattended; see Interactive Mode) | `docker attach` menu |

Both share the chain client, the shared checks and the delivery rules
(`oracle_node/`), so they give the same verdict for the same proof. Run one at
a time: both sign as the same oracle wallet.

The ROS 2 oracle runs two nodes in the `/oracle` namespace: `oracle` (chain,
shared checks, verdicts) and `delivery_validator` (serves
`/oracle/validate/delivery`). The oracle's `validators` parameter maps a
service kind to a validator service, e.g.
`Logistics/ItemTransport=validate/delivery`. A RODEO proof for a kind with no
validator, or whose validator node is not running, is rejected.

### Checks on every RODEO proof

A RODEO proof (a ROS 2 bag written by the robot's executor, see
[../robot-agent/README.md](../robot-agent/README.md)) must pass these before its
service's validator runs:

| Check | Rejects |
|---|---|
| Hash | a file that no longer matches the `#sha256=` in its URI |
| Reuse | a proof already used for another task (hashes are kept in `state/used_proofs.json`) |
| Manifest | a proof for another task, executor, category or task type |
| Parameters | a proof whose parameters differ from the task's (with the service's defaults filled in) |
| Time window | messages recorded before the task's assignment or after the proof's submission (block times, `CLOCK_TOLERANCE_SEC`) |

### Validators

Chosen by the task's category and task type. The rules live in
`oracle_node/validators/`; in the ROS 2 oracle each runs inside a validator node:

| Service | Validator | Checks |
|---|---|---|
| Logistics / ItemTransport | `delivery.py` | arrived at the pick-up, then the drop-off place, within `DELIVERY_PLACE_RADIUS_M` of the places in the service's on-chain description; a package was loaded at pick-up, carried and unloaded at drop-off (deck weight, `DELIVERY_WEIGHT_TOL_KG`, declared weight if given); receipt confirmed at drop-off by the named recipient |

A new service gets a validator by:

- **ROS 2 oracle:** a node (any language) serving `ValidateProof` under the
  oracle's namespace, started from `launch/oracle.launch.py` and listed in the
  `validators` parameter. `rodeo_oracle/delivery_validator.py` is the template.
- **Python oracle:** a module with `@register("Category", "TaskType")`, imported
  in `validators/__init__.py`.

### Legacy proofs

Proofs in the original formats are still accepted while `LEGACY_PROOFS=1` (the
default):

- **ROS 1 bag (.bag)**: the original waste-sorting checks (path length on
  `/odom_mocap`, arm movement on `/vx300s/joint_states`, a correct
  `/disposal_event`), ported to read the bag directly.
- **Power log (.csv)**: energy is computed and the task approved, as before.

They carry no manifest, so a legacy proof passes for **any** task. Set
`LEGACY_PROOFS=0` to refuse them once nothing relies on them.

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

**RODEO proofs** (ROS 2 bag directory, MCAP storage):
```
Proof URI: file:///root/oracle/proofs/task12_panther_20261110T142233#sha256=<hex>
Topics:
  - /rodeo/manifest        (rodeo_interfaces/ProofManifest)  task, executor, parameters
  - /rodeo/pose            (geometry_msgs/PoseStamped)       map frame
  - /rodeo/events          (rodeo_interfaces/TaskEvent)      arrive, depart, say, confirm
  - /rodeo/payload_weight  (rodeo_interfaces/PayloadWeight)  delivery only
```

**Legacy ROS 1 bags:**
```
Proof URI: file:///root/oracle/proofs/task_tid10_20250910_145742.bag
Topics:
  - /odom_mocap (nav_msgs/Odometry)
  - /vx300s/joint_states (sensor_msgs/JointState)
  - /disposal_event (std_msgs/String)
```

The proofs directory holds two example legacy bags: `task_tid10_20250910_145742.bag`
passes the waste-sorting checks, `task_tid1_20250904_164349.bag` fails them (no
correct disposal event).

**Legacy power CSV files:**
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

The ROS 2 oracle runs unattended. For the menu (inbox, manual approve or
reject, re-validate), start the Python console inside its container without a
second chain watcher:

```bash
docker exec -it -e ORACLE_WATCH=0 rodeo-oracle python3 -m oracle_node.main
```

With the Python oracle, attach to it instead: `docker attach rodeo-oracle-python`.

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
# Open the console (ROS 2 oracle; with the Python oracle: docker attach rodeo-oracle-python)
docker exec -it -e ORACLE_WATCH=0 rodeo-oracle python3 -m oracle_node.main

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
├── docker/                    # Dockerfile (ROS 2, default), Dockerfile.python, one compose file
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example           # Configuration template
│   └── oracle-docker.sh       # Helper script
├── ros2_ws/src/rodeo_oracle/  # ROS 2 oracle: oracle node, delivery_validator node, launch
├── oracle_node/               # Python oracle and the logic both oracles share
│   ├── main.py                # Entry point
│   ├── settings.py            # Configuration from the environment
│   ├── chain.py               # Contract access, task time windows, service descriptions
│   ├── events.py              # Event monitoring
│   ├── controller.py          # Routes each proof to its checks
│   ├── proofs.py              # Reads proofs (rosbags)
│   ├── checks.py              # Shared checks on RODEO proofs
│   ├── power_csv.py           # Energy from power CSVs
│   └── validators/            # delivery.py, waste_ros1.py, energy_csv.py
├── proofs/                    # Proofs (examples committed; generated ones ignored)
├── state/                     # Hashes of used proofs (created at run time, not committed)
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
