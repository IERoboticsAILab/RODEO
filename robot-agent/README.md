# RODEO robot standard

What a robot implements to join RODEO. Matching stays on-chain; every robot runs
its own **bridge** (`dao-bridge/ros2-eth-bridge`, one wallet), its own **agent**
(generic, configured by `services.yaml`) and an **executor** (robot-specific,
serves `execute_task`). Nothing here is specific to one robot.

```
robot-agent/
├── config/panther/services.yaml      what the Panther offers
├── docker/                           agent image (also holds the fake executor)
└── ros2_ws/src/
    ├── rodeo_interfaces/             ROS 2: ExecuteTask action, proof messages
    ├── rodeo_common/                 plain Python (no ROS): the conventions below
    └── rodeo_agent/                  the agent, ProofWriter, fake executor
```

`rodeo_common` has no ROS imports, so the oracle and other tools can use it
directly (`pip install robot-agent/ros2_ws/src/rodeo_common`).

## 1. services.yaml

One file per robot: name (becomes the ROS namespace), wallet, the services it
offers, its places and its charging limit. See `config/panther/services.yaml`
and `rodeo_common/services_config.py`, which validates it.

A service may declare parameters of type `place`, `text` or `number`, each
optionally with a `default` used when a task doesn't give it (for example a task
posted with a free-text description). Fixed services (TIAGo's tour, the drone
patrol) declare none.

Each place has a `label`, the executor's own `waypoint` name, and `xy`, its
map-frame position, which the oracle checks poses against. The Panther's come
from the web app's `waypoints_captured.yaml`.

## 2. The service's on-chain description

When the agent registers a service, its `description` is JSON instead of free
text (`rodeo_common/service_description.py`):

```json
{"v": 1, "robot": "panther", "summary": "...",
 "params": {"pickup": {"type": "place", "label": "Pick-up place", "optional": false}, "...": {}},
 "places": {"samuel_desk": {"label": "Samuel's desk", "xy": [1.2, 3.4]}, "...": {}},
 "settings": {"wait_s": 60}}
```

Org-web renders the task form from it and the oracle reads place positions from
it, so neither needs any robot-specific configuration. The Panther's description
is about 1 KB.

## 3. Task descriptions

Org-web writes each task's `description` as (`rodeo_common/description.py`):

```json
{"v": 1, "params": {"pickup": "package_pickup", "dropoff": "samuel_desk",
                    "sender": "Farah", "recipient": "Samuel"}, "note": "fragile"}
```

`validate_task_params()` checks it against the service's schema. Anything that
isn't this JSON (every task created so far) parses as a free-text note with no
parameters.

## 4. The execute_task action

Each robot's executor serves `/<robot>/rodeo/execute_task`
(`rodeo_interfaces/action/ExecuteTask`). The agent sends the task's ID, type,
parameters and note, plus the robot's wallet, name and the proof directory. The
executor does the work, writes the proof bag, and returns its path. Feedback
reports the current stage.

## 5. Proofs

A ROS 2 bag written by the executor (`rodeo_common/proof.py`):

| Topic | Type | Content |
|---|---|---|
| `/rodeo/manifest` | `rodeo_interfaces/ProofManifest` | once: task ID, executor wallet, robot, type, parameters, start time |
| `/rodeo/pose` | `geometry_msgs/PoseStamped` | map frame, 1–2 Hz |
| `/rodeo/events` | `rodeo_interfaces/TaskEvent` | arrive, depart, say, confirm, note |
| `/rodeo/payload_weight` | `rodeo_interfaces/PayloadWeight` | delivery only: deck load, `stable` when stopped |

The agent submits `file://<path>#sha256=<hash>`. The hash covers the file, or
every file of a bag directory, so the proof can't be swapped after submission.
The manifest binds it to one task.

## 6. The agent

`rodeo_agent` is generic: one per robot, next to that robot's bridge, in the
same namespace, configured only by `services.yaml`.

| When | What it does |
|---|---|
| start | Makes the robot's on-chain services match `services.yaml`. It reuses a service whose name, kind, price and description all match, reactivates it if inactive, and otherwise registers a new one, since the contract has no update call. Stale duplicates and own services of kinds not in `services.yaml` are deactivated. It then queues any task assigned to this wallet while the agent was down. |
| assignment | Reads the task, resolves its parameters against the service's schema (defaults filled in), marks the robot's other services busy, and queues it. Tasks run one at a time. |
| execution | Sends `rodeo/execute_task` to the executor, hashes the proof the executor returns, and submits `file://<path>#sha256=<hash>`. |
| verdict | On `task_verified` / `task_rejected`, frees the other services. The contract frees the task's own service. |
| shutdown | On SIGTERM or SIGINT, deactivates the robot's services, so no task is assigned while it is down. |

It follows the project's assumption that an online robot can finish its tasks.
A task with invalid parameters, or one the executor fails, is logged and left
for a person: the contract has no way for the robot to hand a task back.

**Limitation.** Freeing a service with `setBusy(false)` does not make the
contract look for waiting tasks. A task that queued for one of the robot's
other services while they were marked busy is assigned at the next contract
event (a new task, a registration or a completed task). This only matters for
robots with more than one service.

### Run it

```bash
cd robot-agent/docker
cp .env.example .env        # ROS_DOMAIN_ID, ROBOT_NAMESPACE, SERVICES_FILE (match the bridge)
docker compose up -d --build
docker logs -f rodeo-agent  # "ready - waiting for assignments"
```

The agent runs as the container's main process, not through `ros2 launch`, so
`docker stop` reaches it and it can deactivate its services first (it gets
30 s). The proof folder `oracle/proofs/` is mounted at `/root/oracle/proofs`
in the agent, the executors and the oracle.

### Writing an executor

A robot's executor serves `/<robot>/rodeo/execute_task` and, for each goal:

1. does the task, publishing feedback stages;
2. writes the proof with `rodeo_agent.proof_writer.ProofWriter` into
   `goal.proof_dir`; the writer adds the manifest itself;
3. returns `success` and the proof's path.

```python
from rodeo_agent.proof_writer import ProofWriter
from rodeo_interfaces.msg import TaskEvent

with ProofWriter(goal.proof_dir, goal) as proof:
    proof.pose(x, y, yaw)                                  # 1-2 Hz while moving
    proof.event(TaskEvent.ARRIVE, place="package_pickup")
    proof.weight(1.2, stable=True)                         # delivery only
result = ExecuteTask.Result(success=True, proof_path=proof.path)
```

What the oracle then checks is in `oracle/README.md`. For a delivery, record:
ARRIVE and DEPART events with place ids; poses while moving and at each stop;
stable weight readings at the start, at the pick-up after loading, and at the
drop-off before and after unloading; and a CONFIRM event at the drop-off with
the recipient as actor.

`rodeo_agent/fake_executor.py` is a complete example, and the stand-in robot
used by the demo in `quick-start/`.
