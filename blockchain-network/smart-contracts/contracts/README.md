# Smart Contract Architecture

Solidity smart contracts implementing the RODEO decentralized organization for autonomous robot coordination.

## Overview

The RODEO smart contract system consists of four main contracts that work together to enable decentralized task coordination and execution for autonomous robots.

```
┌─────────────────────────────────────────────────────┐
│                   Organization.sol                   │
│            (Main Coordinator - 252 LOC)              │
│  - Manages TaskManager & ServiceManager              │
│  - Owner-controlled operations                       │
│  - Task-Service assignment mapping                   │
└──────────────┬──────────────────────┬────────────────┘
               │                      │
       ┌───────▼─────────┐    ┌──────▼──────────┐
       │ TaskManager.sol │    │ServiceManager.sol│
       │   (232 LOC)     │    │    (135 LOC)     │
       │                 │    │                  │
       │ - Task lifecycle│    │ - Service registry│
       │ - Escrow mgmt   │    │ - Availability   │
       │ - Oracle verify │    │ - Provider types │
       └────────┬────────┘    └──────────────────┘
                │
         ┌──────▼──────┐
         │ IECoin.sol  │
         │  (14 LOC)   │
         │  ERC20 Token│
         └─────────────┘
```

## Contract Responsibilities

### 1. Organization.sol (Entry Point)
**Location:** `Organization.sol`

The main coordinator contract that orchestrates all operations in the system.

**Key Responsibilities:**
- Orchestrates all operations
- Wraps TaskManager & ServiceManager calls
- Maintains task↔service mappings
- Owner: Robot fleet manager/DAO

**Main Functions:**
- `deposit(amount)` - Deposit IEC tokens for escrow
- `registerTask(...)` - Create new task with reward
- `matchTaskWithService(taskId, serviceId)` - Assign service to task
- `unassignTask(taskId)` - Cancel assignment, refund escrow
- `removeTask(taskId)` - Delete unassigned task, refund escrow

### 2. TaskManager.sol (Task Lifecycle)
**Location:** `TaskManager.sol`

Manages the complete lifecycle of tasks from registration to completion, including escrow management.

**Key Responsibilities:**
- Registers tasks with escrow
- Assigns executors
- Handles proof submission
- Oracle verification flow
- Task states: Unassigned → Assigned → Executed

**Main Functions:**
- `submitProof(taskId, proofURI)` - Submit completion proof
- `verifyTask(taskId)` - Oracle approves proof
- `rejectProof(taskId, reason)` - Oracle rejects proof
- `completeTask(taskId)` - Release payment to executor
- `getTotalTasks()` - Get total task count
- `getTask(taskId)` - Get task details
- `getTasksByCreator(creator)` - Get tasks by creator

### 3. ServiceManager.sol (Service Registry)
**Location:** `ServiceManager.sol`

Maintains a registry of available services (robots, humans, organizations) and their capabilities.

**Key Responsibilities:**
- Service registration
- Category/type matching
- Busy/available status
- Provider types: Robot, Human, Organization

**Main Functions:**
- `registerService(...)` - Register robot capability
- `setBusy(serviceId, isBusy)` - Update availability
- `removeService(serviceId)` - Unregister service
- `getServiceCount()` - Get total service count
- `getService(serviceId)` - Get service details
- `getServicesByCreator(creator)` - Get services by creator

### 4. IECoin.sol (Token Economy)
**Location:** `IECoin.sol`

Standard ERC20 token used for task rewards and service payments.

**Key Responsibilities:**
- Standard ERC20 token implementation
- Used for task rewards & service payments
- Initial supply minted to deployer

**Standard ERC20 Functions:**
- `transfer`, `approve`, `balanceOf`, `allowance`, etc.
- See [OpenZeppelin ERC20 docs](https://docs.openzeppelin.com/contracts/4.x/api/token/erc20)

---

## Workflows

### Complete Task Workflow Example

```solidity
// 1. Organization deposits tokens for escrow
Organization.deposit(1000 IEC)

// 2. Register a task (funds escrowed immediately)
taskId = Organization.registerTask(
  description: "Deliver package to Room 301",
  category: "Logistics",
  taskType: "Delivery",
  reward: 500
) // Returns: 1

// 3. Robot registers a service
ServiceManager.registerService(
  name: "Delivery Bot A",
  category: "Logistics", 
  serviceType: "Delivery",
  price: 500,
  providerType: Robot
) // Returns: 1

// 4. Organization matches task to service
Organization.matchTaskWithService(taskId: 1, serviceId: 1)

// 5. Robot executes task (off-chain navigation, pickup, delivery)

// 6. Robot submits proof
TaskManager.submitProof(taskId: 1, proofURI: "ipfs://Qm...")

// 7. Oracle verifies and completes task
TaskManager.verifyTask(taskId: 1) // Called by oracle
TaskManager.completeTask(taskId: 1) // Payment released to executor
```

### Task States & Transitions

```
Unassigned ──matching──> Assigned ──execution──> Executed
    │                        │                      │
    ├─remove────> [Deleted]  │                      │
    │                        │                      │
    │                        ├─unassign──> Unassigned
    │                        │                      │
    │                        └─────────────────────┘
    │                                               │
    └───────────────────verify───────────────> Completed
                                                    │
                                            payment released
```

### Escrow Mechanism

#### When are funds locked?
- ✅ Immediately upon `registerTask()` call
- Creator must pre-approve Organization contract
- TaskManager pulls funds from Organization

#### When are funds released?
- ✅ Task completed: Payment to executor
- ✅ Task removed (unassigned): Refund to creator
- ✅ Task unassigned: Refund to creator
- ✅ Proof rejected: Refund to creator

---

## Events

Each contract emits events for important state changes:

### Organization.sol Events
- `TaskRegistered(taskId, creator, reward)`
- `TaskMatched(taskId, serviceId)`
- `TaskUnassigned(taskId)`
- `TaskRemoved(taskId)`

### TaskManager.sol Events
- `TaskCreated(taskId, creator, reward)`
- `TaskAssigned(taskId, executor)`
- `ProofSubmitted(taskId, proofURI)`
- `TaskVerified(taskId)`
- `ProofRejected(taskId, reason)`
- `TaskCompleted(taskId, executor, reward)`

### ServiceManager.sol Events
- `ServiceRegistered(serviceId, creator, category, serviceType)`
- `ServiceStatusChanged(serviceId, isBusy)`
- `ServiceRemoved(serviceId)`

---

## Contract Interfaces

The `templates/` directory contains interface definitions for implementing custom policies:

- `ICoordinator.sol` - Coordinator interface
- `IMatchingPolicy.sol` - Task-service matching policies
- `IOraclePolicy.sol` - Oracle verification policies
- `IPricingPolicy.sol` - Dynamic pricing policies

These can be extended for custom implementations.

---

## License

MIT License - See [LICENSE](../../../LICENSE)
