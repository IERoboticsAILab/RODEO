# Quick Start: demo without a robot

The demo runs a robot's RODEO software exactly as on a real robot, with a fake
executor standing in for the robot itself, and the institution's charging
station next to it:

```
Panther:  bridge (robot wallet)        ←→  agent  ←→  fake executor (simulated robot and battery)
Station:  bridge (institution wallet)  ←→  agent  ←→  station executor (simulated charger)
```

- The **agent** (`robot-agent/`) registers the robot's services from its
  `services.yaml`, receives assignments, sends each task to the executor,
  hashes the proof and submits it, and handles the oracle's verdict.
- The **fake executor** serves `rodeo/execute_task` like a real robot would: in
  about 15 s it "drives" to the pick-up place, loads, drives to the drop-off
  place, unloads and records the recipient's confirmation, writing a standard
  RODEO proof bag along the way.

It uses the Panther's `services.yaml` (Delivery service, nine lab places), so a
task runs exactly as it will on the Panther, minus the driving. Each delivery
uses 40 % of the simulated battery; below 30 % the Panther's agent takes the
robot offline, docks, pays the station 20 IEC and comes back online once the
oracle has verified the charge. Deliveries posted meanwhile wait and are then
assigned. It is also the
acceptance test for the bridge and the agent: a change is good when this run
still ends with the task verified.

## Run it

Prerequisites (see the top-level README): Ganache with the contracts deployed,
org-web, the oracle and the ROS 2 bridge (the Panther's) running, and the
station's keystore created once:

```bash
python3 dao-bridge/ros2-eth-bridge/scripts/make_wallet.py \
  --key 0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba \
  --out ~/.ros_eth/station_wallet.json          # Ganache account #5 (institution), Enter for no passphrase
```

```bash
cd quick-start/docker
./demo.sh build      # first time, or after code changes
./demo.sh start
./demo.sh logs
```

The agent logs `register service 'Delivery' ...: ok` (or reuses the service
it registered before) and then `ready - waiting for assignments`. Create a task
in org-web (`http://localhost:8080`, Tasks tab):

1. In **Service**, pick `Delivery (Logistics/ItemTransport) - from 100 IEC`.
   The list shows only services that are online; it appears once the agent has
   registered the Panther's service.
2. Choose the **pick-up place** and **Deliver to** from the dropdowns (they
   default to package pick-up and package drop-off), and optionally the sender,
   recipient and package weight.
3. Add a **note** if you like; the **reward** is pre-filled with the service's
   price.
4. Click **Create task**.

The run succeeds when the agent logs `task N: VERIFIED - reward paid`. After
the second task, it logs `charging (battery at 20 %)`, then
`charging task N: VERIFIED - station paid`. To charge without waiting for the
battery, run
`docker exec rodeo-demo-agent bash -ic "ros2 service call /rodeo/request_charging std_srvs/srv/Trigger"`.
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
