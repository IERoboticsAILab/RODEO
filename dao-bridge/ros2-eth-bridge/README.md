# ROS 2 – Ethereum bridge (RODEO, ROS 2 Humble)

ROS 2 port of the original ROS 1 Noetic `ros-eth-bridge` (still on the `main`
branch). It exposes the same actions, services and topics, so a robot talks to
the RODEO contracts the same way it did through the ROS 1 bridge.

```
ros2_ws/src/
├── ros_eth_msgs/      messages, services, actions (ament_cmake)
└── ros_eth_bridge/    dao_listener + dao_writer nodes (ament_python)
    ├── eth/           chain layer, copied unchanged from the ROS 1 bridge (no ROS imports)
    ├── abi/           contract ABIs (identical to the ROS 1 copies)
    ├── config/dao.yaml
    └── launch/ros_eth_gateway.launch.py
docker/                Humble image, compose file, mounted dao.yaml
scripts/make_wallet.py the robot's encrypted keystore
```

One bridge instance holds one wallet. Run one per robot, each in its own namespace.

## Interface

All names are relative, so the namespace decides where they appear. Without a
namespace they are the ROS 1 names (`/dao/...`); with namespace `panther` they
are `/panther/dao/...`.

| Kind | Names |
|---|---|
| Actions (dao_writer) | `dao/register_service_action`, `dao/register_task_action`, `dao/submit_proof_action`, `dao/remove_task_action`, `dao/remove_service_action`, `dao/activate_service_action`, `dao/activate_task_action`, `dao/set_service_busy_action`, `dao/transfer_token_action`, `dao/approve_spender_action` |
| Services | `dao/get_task_by_id`, `dao/get_all_tasks`, `dao/get_tasks_by_creator`, `dao/get_service_by_id`, `dao/get_all_services`, `dao/get_services_by_creator` (dao_listener); `dao/get_balance`, `dao/get_allowance` (dao_writer) |
| Topics (dao_listener) | `dao/task_registered`, `dao/task_assigned`, `dao/task_unassigned`, `dao/task_verified`, `dao/task_rejected`, `dao/service_registered`, `dao/service_busy` |

## Differences from the ROS 1 bridge

1. **Own assignments only.** `dao/task_assigned` is published only when the
   task's executor is this bridge's wallet (parameter `own_assignments_only`,
   default `true`). Each robot's agent sees only its own work.
2. **Integer types.** Every task ID, service ID and block number is `uint64`,
   and every `min_confirmations` is `uint32`. ROS 1 mixed `uint32` and `uint64`
   (e.g. `TaskAssignment.task_id` was `uint64` but `GetTask.task_id` `uint32`).
3. **Passphrase.** Taken from `ETH_WALLET_PASSPHRASE` (or the `wallet_passphrase`
   parameter); the empty passphrase hard-coded in the ROS 1 launch file is gone.
   The wallet is unlocked at start-up, so a wrong passphrase stops `dao_writer`
   immediately instead of failing the first transaction.
4. **Concurrent goals.** Goals run side by side on a multi-threaded executor.
   The ROS 1 `SimpleActionServer` replaced a running goal when a new one
   arrived. Transactions are still serialised by the per-wallet nonce lock.
5. **Event checkpoint per namespace** (`~/.ros_eth/event_checkpoint_<ns>.json`),
   so several bridges on one machine don't share a cursor.
6. **Relative ABI paths** in `dao.yaml` (`abi/TaskManager.json`) resolve against
   the installed package.

## Run with Docker

Prerequisites: Ganache running with the contracts deployed, and org-web and the
oracle up (see the top-level README).

```bash
# robot keystore, once (press Enter for an empty dev passphrase)
pip3 install eth-account
python3 dao-bridge/ros2-eth-bridge/scripts/make_wallet.py   # -> ~/.ros_eth/wallet.json

cd dao-bridge/ros2-eth-bridge/docker
cp .env.example .env            # optional: ROS_DOMAIN_ID, ROBOT_NAMESPACE, passphrase
docker compose up -d --build
docker logs -f ros2-eth-bridge  # expect "dao_listener ready" and "dao_writer ready"
```

### Acceptance test: the ROS 2 robot emulator

```bash
cd quick-start/docker
./robot-emulator.sh build
./robot-emulator.sh start
./robot-emulator.sh logs
```

Then create the task in org-web (Category `Logistics`, Task Type
`ItemTransport`, Reward `100`). The run passes when the emulator logs
`Task 1 verified — reward received!` and the oracle logs `APPROVED`.

The emulator must use the bridge's `ROS_DOMAIN_ID` and `ROBOT_NAMESPACE`; both
compose files default to domain 40 and no namespace.

## Run without Docker

```bash
pip3 install web3==6.11.4 websockets==13.1
pip3 install --no-deps eth-account==0.13.7
cd dao-bridge/ros2-eth-bridge/ros2_ws
source /opt/ros/humble/setup.bash && colcon build && source install/setup.bash
ros2 launch ros_eth_bridge ros_eth_gateway.launch.py \
    config_file:=$PWD/../docker/configs/dao.yaml namespace:=panther
```

## Notes

* **Library versions.** web3 6.11.4 requires `hexbytes<0.4` and eth-account
  0.13.7 requires `hexbytes>=1.2`. The ROS 1 image ends up with hexbytes 0.3.1
  and works; a modern pip refuses the pair, so eth-account is installed with
  `--no-deps`. Moving to web3 7 would remove this, but needs the `eth/` layer
  checked against web3 7 first.
* **Oracle.** The oracle still validates ROS 1 bags with `rosbag play`, which
  needs a ROS 1 master. The ROS 1 bridge used to start one; the oracle's
  entrypoint now starts its own when none is running. The oracle also reads
  its contract ABIs from this package's `abi/` folder.
* **DDS between containers.** Both compose files use `network_mode: host` and
  `ipc: host`, which ROS 2's shared-memory transport needs across containers.
* **Addresses.** `scripts/update-addresses.sh` updates `docker/configs/dao.yaml`
  together with the other configs. The committed addresses are the ones a fresh
  Ganache chain produces with the standard deploy.
