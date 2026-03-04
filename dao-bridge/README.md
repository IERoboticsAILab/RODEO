# DAO Bridge

Integration layer connecting RODEO blockchain infrastructure with robot systems and human operators. Provides both programmatic (ROS) and web-based interfaces for decentralized task coordination.

## Components

### [ros-eth-bridge](ros-eth-bridge/)
ROS Noetic package enabling robots to interact with smart contracts through action servers and event publishers. Implements bidirectional Web3.py communication for autonomous agent participation in the DAO.

**Key Features:**
- 10 action servers for blockchain write operations (tasks, services, tokens)
- Real-time event streaming from blockchain to ROS topics
- Transaction management with nonce serialization
- Support for both WebSocket and HTTP providers

**Use Cases:** Autonomous robots registering services, bidding on tasks, submitting proofs, managing IECoin balances

### [org-web](org-web/)
Web dashboard for human operators to monitor and manage DAO activities. Combines FastAPI backend with Next.js frontend in a single Docker container.

**Key Features:**
- Task and service registry management
- Token holder visualization
- Transaction history monitoring
- RESTful API for external integrations

**Use Cases:** Organization administrators, human coordinators, system monitoring

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  Robot (ROS)    │         │  Human Operator  │
│                 │         │                  │
│  ros-eth-bridge │         │    org-web       │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │      Web3.py/HTTP         │
         └───────────┬───────────────┘
                     │
         ┌───────────▼────────────┐
         │  Ethereum Blockchain   │
         │  (Ganache/Public Net)  │
         │                        │
         │  • Organization.sol    │
         │  • TaskManager.sol     │
         │  • ServiceManager.sol  │
         │  • IECoin.sol          │
         └────────────────────────┘
```

## Quick Start

**Prerequisites:**
- Docker and Docker Compose
- Ethereum compatible network (see [../blockchain-network/ganache-docker](../blockchain-network/ganache-docker/))
- Deployed smart contracts with addresses (see [../blockchain-network/smart-contracts](../blockchain-network/smart-contracts/))
- Funded robot, organization and human wallets with IEC

### ROS Bridge (Docker)

```bash
cd ros-eth-bridge/docker

# 1. Update contract addresses in config
nano configs/dao.yaml

# 2. Setup wallet (if not already done)
mkdir -p ~/.ros_eth
python3 configs/make_wallet.py

# 3. Build and start
./ros-eth-bridge-docker.sh build
./ros-eth-bridge-docker.sh start

# 4. Verify
./ros-eth-bridge-docker.sh logs
```

📖 **See [ros-eth-bridge/docker/QUICKSTART.md](ros-eth-bridge/docker/QUICKSTART.md) for detailed setup**

### Web Console (Docker)

```bash
cd org-web
docker build -t org-console .
docker run --env-file .env -p 8080:80 org-console
```

Access dashboard at `http://localhost:8080`

## Configuration

Both components require contract addresses from deployment:

**ROS Bridge:** `ros-eth-bridge/docker/configs/dao.yaml`  
**Web Console:** `org-web/.env` (environment variables)

### Update Contract Addresses

After deploying smart contracts, update the configuration files:

**For ROS Bridge:**
```bash
cd ros-eth-bridge/docker
nano configs/dao.yaml

# Update these addresses:
contracts:
  iecoin: "0x..."              # From deployments/1337.json
  organization: "0x..."
  task_manager: "0x..."
  service_manager: "0x..."
```

**For Web Console:**
```bash
cd org-web
cp .env.example .env
nano .env

# Update these addresses:
RPC_URL=http://localhost:8545
ORGANIZATION_ADDRESS=0x...    # From deployments/1337.json
IECOIN_ADDRESS=0x...
ORGANIZATION_WALLET_PUBLIC=0x...   # Your organization wallet
ORGANIZATION_WALLET_PRIVATE=0x...  # Your private key (keep secure!)
```

💡 **Tip:** Get contract addresses from `blockchain-network/smart-contracts/deployments/1337.json`

## Integration Patterns

### Robot-to-Blockchain

Robots use ROS action servers to perform transactions.

**Example: Register a robot service**
```bash
# Register a delivery robot service
rostopic pub -1 /dao/register_service_action/goal ros_eth_msgs/RegisterServiceActionGoal \
  '{goal: {name: "DeliveryBot_A", category: "Logistics", service_type: "Delivery", price: "50"}}'
```

**Other available actions:**
```bash
# Register a task
rostopic pub -1 /dao/register_task_action/goal ros_eth_msgs/RegisterTaskActionGoal \
  '{goal: {description: "Deliver package to Room 301", category: "Logistics", task_type: "Delivery", reward: "50", min_confirmations: 1}}'

# Submit proof of task completion
rostopic pub -1 /dao/submit_proof_action/goal ros_eth_msgs/SubmitProofActionGoal \
  '{goal: {task_id: 1, proof_uri: "ipfs://Qm...", min_confirmations: 1}}'

# Transfer IECoin tokens
rostopic pub -1 /dao/transfer_token_action/goal ros_eth_msgs/TransferTokenActionGoal \
  '{goal: {recipient: "0x...", amount: "100", min_confirmations: 1}}'
```

**Query blockchain state:**
```bash
# Get all services
rosservice call /dao/get_all_services

# Get all tasks
rosservice call /dao/get_all_tasks

# Check token balance
rosservice call /dao/get_balance '{address: "0x..."}'
```

### Blockchain-to-Robot

Robots subscribe to event topics for task assignments:
```bash
# Monitor task assignments
rostopic echo /dao/task_assigned

# Monitor service registrations
rostopic echo /dao/service_registered

# Monitor task verifications
rostopic echo /dao/task_verified
```

## Documentation

- **ROS Bridge:** [ros-eth-bridge/README.md](ros-eth-bridge/README.md)
- **Web Console:** [org-web/README.md](org-web/README.md)
- **Smart Contracts:** [../blockchain-network/smart-contracts/README.md](../blockchain-network/smart-contracts/README.md)
