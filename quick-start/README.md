# Quick Start: demo without a robot

The demo runs a robot's RODEO software exactly as on a real robot, with a fake
executor standing in for the robot itself:

```
bridge (wallet)  ←→  agent  ←→  fake executor
```

- The **agent** (`robot-agent/`) registers the robot's services from its
  `services.yaml`, receives assignments, sends each task to the executor,
  hashes the proof and submits it, and handles the oracle's verdict.
- The **fake executor** serves `rodeo/execute_task` like a real robot would: in
  about 15 s it "drives" to the pick-up place, loads, drives to the drop-off
  place, unloads and records the recipient's confirmation, writing a standard
  RODEO proof bag along the way.

It uses the Panther's `services.yaml` (Delivery service, nine lab places), so a
task runs exactly as it will on the Panther, minus the driving. It is also the
acceptance test for the bridge and the agent: a change is good when this run
still ends with the task verified.

## Run it

Prerequisites (see the top-level README): Ganache with the contracts deployed,
org-web, the oracle and the ROS 2 bridge running.

```bash
cd quick-start/docker
./demo.sh build      # first time, or after code changes
./demo.sh start
./demo.sh logs
```

The agent logs `register service 'Delivery' ...: ok` (or reuses the service
it registered before) and then `ready - waiting for assignments`. Create a task
in org-web (`http://localhost:8080`, Tasks tab):

| Field | Value |
|---|---|
| Title | Package delivery |
| Description | Package delivery |
| Category | Logistics |
| Type | ItemTransport |
| Reward | 100 |

Category and Type must match exactly: that is how the contract matches the task
to the service. A free-text description runs the Delivery service with its
default places (package pick-up to package drop-off). To choose the places, put
JSON in the Description field instead:

```json
{"v": 1, "params": {"pickup": "farah_desk", "dropoff": "samuel_desk", "sender": "Farah", "recipient": "Samuel"}, "note": "fragile"}
```

The run succeeds when the agent logs `task N: VERIFIED - reward paid`.
`./demo.sh stop` stops both containers; the agent deactivates its service
first, so no new task is assigned while it is down.

## Settings

| Setting | Default | Notes |
|---|---|---|
| `ROS_DOMAIN_ID` | 40 | must match the bridge |
| `ROBOT_NAMESPACE` | none | must match the bridge, e.g. `panther` |
| `PROOF_MODE` | `rodeo` | see below |
| `SERVICES_FILE` | the Panther's `services.yaml` | any robot's `services.yaml` |

Set them in the shell or in `quick-start/docker/.env`.

**Proof mode.** In `rodeo` mode the agent submits the RODEO proof the fake
executor writes to `oracle/proofs/task<id>_<robot>_<time>/`, and the oracle
runs its shared checks and the delivery validator on it. `legacy` mode submits
the ROS 1 bag from the original waste-sorting demo instead; the oracle accepts
it only while `LEGACY_PROOFS=1`, and since that bag is not bound to a task it
passes for any task.

## Inspect a proof

```bash
docker exec rodeo-demo-agent bash -ic "ros2 bag info /root/oracle/proofs/task1_panther_<time>"
```

It holds `/rodeo/manifest`, `/rodeo/pose`, `/rodeo/events` and
`/rodeo/payload_weight`; see `robot-agent/README.md`.
