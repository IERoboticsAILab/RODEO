# DAO Bridge

Integration layer connecting the RODEO contracts with robots and human operators:
a ROS 2 interface for robots and a web console for people.

## Components

### [ros2-eth-bridge](ros2-eth-bridge/)
ROS 2 Humble package through which a robot uses the contracts: action servers
for every write operation, query services, and event topics. One instance holds
one wallet; run one per robot, each in its own namespace.

**Key features:**
- 10 action servers for blockchain writes (tasks, services, tokens)
- 8 query services and 7 event topics
- `task_assigned` delivered only to the bridge whose wallet is the executor
- Transaction management with per-wallet nonce serialisation

### [org-web](org-web/)
Web dashboard for human operators: FastAPI backend and Next.js frontend in a
single Docker container.

**Key features:**
- Task and service registry management
- Token holder visualisation
- RESTful API for external integrations

## Architecture

```
┌──────────────────┐         ┌──────────────────┐
│  Robot (ROS 2)   │         │  Human Operator  │
│                  │         │                  │
│  ros2-eth-bridge │         │     org-web      │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │       Web3.py / HTTP       │
         └─────────────┬──────────────┘
                       │
          ┌────────────▼───────────┐
          │  Ethereum blockchain   │
          │  (Ganache / public)    │
          │                        │
          │  • Organization.sol    │
          │  • TaskManager.sol     │
          │  • ServiceManager.sol  │
          │  • IECoin.sol          │
          └────────────────────────┘
```

## Quick Start

**Prerequisites:** Docker with Compose v2, Ganache running with the contracts
deployed (see [../blockchain-network](../blockchain-network/)), and funded robot,
organization and human wallets.

### ROS 2 bridge (Docker)

```bash
cd ros2-eth-bridge

# 1. Robot keystore (once; press Enter for an empty dev passphrase)
pip3 install eth-account
python3 scripts/make_wallet.py

# 2. Contract addresses: docker/configs/dao.yaml
#    (scripts/update-addresses.sh at the repo root fills it in)

# 3. Build and start
cd docker && docker compose up -d --build
docker logs -f ros2-eth-bridge     # "dao_listener ready" and "dao_writer ready"
```

📖 See [ros2-eth-bridge/README.md](ros2-eth-bridge/README.md) for the interface and options.

### Web console (Docker)

```bash
cd org-web
docker compose up -d --build
```

Dashboard at `http://localhost:8080`.

## Configuration

Both components need the deployed contract addresses:

- **ROS 2 bridge:** `ros2-eth-bridge/docker/configs/dao.yaml`
- **Web console:** `org-web/.env`

After deploying, run from the repository root:

```bash
./scripts/update-addresses.sh blockchain-network/smart-contracts/deployments/1337.json
```

💡 On a fresh Ganache chain the standard deployment always produces the same
addresses, which are the ones already committed.

## Integration patterns

The commands below run inside the bridge container
(`docker exec -it ros2-eth-bridge bash`) or on any machine on the same
`ROS_DOMAIN_ID` with `ros_eth_msgs` built. With a namespace, prefix the names
(`/panther/dao/...`).

### Robot to blockchain

```bash
# Register a service
ros2 action send_goal /dao/register_service_action ros_eth_msgs/action/RegisterService \
  "{name: 'DeliveryBot_A', description: 'Delivery robot', category: 'Logistics', service_type: 'ItemTransport', price: '50', provider_type: 0, min_confirmations: 1}"

# Register a task (approves the TaskManager for the reward first)
ros2 action send_goal /dao/register_task_action ros_eth_msgs/action/RegisterTask \
  "{description: 'Deliver package to Room 301', category: 'Logistics', task_type: 'ItemTransport', reward: '50', min_confirmations: 1}"

# Submit proof of task completion
ros2 action send_goal /dao/submit_proof_action ros_eth_msgs/action/SubmitProof \
  "{task_id: 1, proof_uri: 'file:///root/oracle/proofs/example.bag', min_confirmations: 1}"

# Transfer IECoin
ros2 action send_goal /dao/transfer_token_action ros_eth_msgs/action/TransferToken \
  "{to: '0x...', amount: '100', min_confirmations: 1}"
```

### Query blockchain state

```bash
ros2 service call /dao/get_all_services ros_eth_msgs/srv/GetAllServices
ros2 service call /dao/get_all_tasks ros_eth_msgs/srv/GetAllTasks
ros2 service call /dao/get_balance ros_eth_msgs/srv/GetBalance "{owner: ''}"   # '' = this wallet
```

### Blockchain to robot

```bash
ros2 topic echo /dao/task_assigned
ros2 topic echo /dao/service_registered
ros2 topic echo /dao/task_verified
```

## Documentation

- **ROS 2 bridge:** [ros2-eth-bridge/README.md](ros2-eth-bridge/README.md)
- **Web console:** [org-web/README.md](org-web/README.md)
- **Smart contracts:** [../blockchain-network/smart-contracts/README.md](../blockchain-network/smart-contracts/README.md)
- **Robot standard (services.yaml, execute_task, proofs):** [../robot-agent/README.md](../robot-agent/README.md)
