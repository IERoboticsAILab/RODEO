# RODEO robot standard

What a robot implements to join RODEO. Matching stays on-chain; every robot runs
its own **bridge** (`dao-bridge/ros2-eth-bridge`, one wallet), its own **agent**
(generic, configured by `services.yaml`) and an **executor** (robot-specific,
serves `execute_task`). Nothing here is specific to one robot.

```
robot-agent/
├── config/panther/services.yaml      what the Panther offers
└── ros2_ws/src/
    ├── rodeo_interfaces/             ROS 2: ExecuteTask action, proof messages
    └── rodeo_common/                 plain Python (no ROS): the conventions below
```

`rodeo_common` has no ROS imports, so the oracle and other tools can use it
directly (`pip install robot-agent/ros2_ws/src/rodeo_common`).

## 1. services.yaml

One file per robot: name (becomes the ROS namespace), wallet, the services it
offers, its places and its charging limit. See `config/panther/services.yaml`
and `rodeo_common/services_config.py`, which validates it.

A service may declare parameters of type `place`, `text` or `number`. Fixed
services (TIAGo's tour, the drone patrol) declare none.

Each place has a `label`, the executor's own `waypoint` name, and `xy`, its
map-frame position, which the oracle checks poses against. For the Panther, `xy`
is still null: copy it from `waypoints_captured.yaml`.

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
