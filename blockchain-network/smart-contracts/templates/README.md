# Smart Contract Templates

Interface templates for building modular and extensible RODEO implementations.

## Overview

This folder contains **Solidity interface templates** that define the architecture for flexible, policy-based decentralized robot organization systems. These interfaces allow you to:

- 🔌 **Plug in custom matching algorithms** (e.g., cheapest service, highest reward, reputation-based)
- 💰 **Implement different pricing models** (fixed price, auction, dynamic pricing)
- ✅ **Add custom oracle policies** (multi-oracle consensus, threshold voting)
- 🏗️ **Build modular extensions** without changing core contracts

## Purpose

The current RODEO implementation (`contracts/` folder) uses a **monolithic architecture** with fixed logic. These templates provide a **blueprint for a modular refactor** where policies can be swapped, upgraded, or customized.

---

## Interface Files

### 1. **ICoordinator.sol**
Main entry point interface for the organization.

**Responsibilities:**
- Wire TaskManager, ServiceManager, and Oracle
- Provide wrapper functions for task/service operations
- Define callback hooks for lifecycle events

**Key Methods:**
```solidity
// Setup
function setTaskManager(address tm) external;
function setServiceManager(address sm) external;
function setOracle(address oracle) external;

// Operations
function registerTask(...) external returns (uint256);
function registerService(...) external returns (uint256);

// Callbacks
function onTaskRegistered(uint256 taskId) external;
function onTaskComplete(uint256 taskId) external;
function onServiceRegistered(uint256 serviceId) external;
```

**Use Case:** Implement a coordinator that delegates to specialized managers and responds to lifecycle events.

---

### 2. **ITaskManager.sol**
Task registry, escrow, and lifecycle management.

**Key Features:**
- Task registration with escrow mechanism
- Executor assignment
- Proof submission and verification
- Task activation/deactivation

**Task Structure:**
```solidity
struct Task {
    uint256 id;
    string description;
    bytes32 categoryHash;
    bytes32 taskTypeHash;
    address creator;
    uint256 reward;
    TaskStatus status;  // Unassigned, Assigned, Executed
    address executor;
    bool active;
    string proofURI;
    address oracle;
    bool verified;
}
```

**Key Methods:**
```solidity
function registerTask(string calldata description, ...) external returns (uint256);
function assignTaskExecutor(uint256 taskId, address executor, uint256 reward) external;
function submitProof(uint256 taskId, string calldata proofURI) external;
function verifyTask(uint256 taskId) external;
function completeTask(uint256 taskId) external;
```

**Use Case:** Build a task manager with custom escrow timing, refund rules, or multi-stage verification.

---

### 3. **IServiceManager.sol**
Service registry and availability management.

**Key Features:**
- Service registration with metadata
- Provider types (Robot, Human, Organization)
- Busy/available status
- Category and type-based indexing

**Service Structure:**
```solidity
struct Service {
    uint256 id;
    string name;
    string description;
    bytes32 categoryHash;
    bytes32 serviceTypeHash;
    uint256 price;
    address creator;
    bool active;
    ProviderType providerType;
    bool busy;
}
```

**Key Methods:**
```solidity
function registerService(...) external returns (uint256);
function setBusy(uint256 serviceId, bool isBusy) external;
function removeService(uint256 serviceId) external;
function getService(uint256 serviceId) external view returns (Service memory);
```

**Use Case:** Implement a service catalog with reputation scoring, SLA tracking, or auction-based pricing.

---

### 4. **IMatchingPolicy.sol**
Pluggable task-service matching logic.

**Purpose:** Decouple matching algorithms from core contracts.

**Methods:**
```solidity
function pickServiceForTask(uint256 taskId) 
    external view 
    returns (uint256 serviceId, uint256 agreedReward);

function pickTaskForService(uint256 serviceId) 
    external view 
    returns (uint256 taskId, uint256 agreedReward);
```

**Example Implementations:**

1. **CheapestServicePolicy**
   ```solidity
   // Match task to lowest-priced available service
   function pickServiceForTask(uint256 taskId) external view {
       // Find service with min price where:
       // - category/type match
       // - service.price <= task.reward
       // - service.busy == false
   }
   ```

2. **HighestRewardPolicy**
   ```solidity
   // Match service to highest-paying task
   function pickTaskForService(uint256 serviceId) external view {
       // Find task with max reward where:
       // - category/type match
       // - task.reward >= service.price
       // - task.status == Unassigned
   }
   ```

3. **ReputationBasedPolicy**
   ```solidity
   // Match based on robot reputation scores
   ```

4. **FairQueuePolicy**
   ```solidity
   // FIFO matching with fairness guarantees
   ```

**Use Case:** Experiment with different matching strategies without redeploying core contracts.

---

### 5. **IPricingPolicy.sol**
Price negotiation and validation logic.

**Purpose:** Determine if service price is acceptable and calculate final payout.

**Method:**
```solidity
function priceTask(uint256 taskBudget, uint256 servicePrice) 
    external pure 
    returns (bool ok, uint256 agreedReward);
```

**Example Implementations:**

1. **ExactPricePolicy**
   ```solidity
   // Require exact match: taskBudget == servicePrice
   function priceTask(uint256 taskBudget, uint256 servicePrice) {
       return (taskBudget == servicePrice, servicePrice);
   }
   ```

2. **MaxBudgetPolicy**
   ```solidity
   // Accept if servicePrice <= taskBudget
   function priceTask(uint256 taskBudget, uint256 servicePrice) {
       bool ok = servicePrice <= taskBudget;
       return (ok, servicePrice);
   }
   ```

3. **NegotiatedDiscountPolicy**
   ```solidity
   // Apply 10% discount for high-reputation services
   function priceTask(uint256 taskBudget, uint256 servicePrice) {
       uint256 discount = getServiceReputation(msg.sender) > 90 ? 10 : 0;
       uint256 finalPrice = servicePrice * (100 - discount) / 100;
       return (finalPrice <= taskBudget, finalPrice);
   }
   ```

**Use Case:** Implement dynamic pricing, auctions, or discount mechanisms.

---

### 6. **IOraclePolicy.sol**
Oracle verification and authorization.

**Purpose:** Flexible oracle configurations (single, multi-sig, DAO vote).

**Methods:**
```solidity
function canFinalize(address caller) external view returns (bool);
function normalizeReason(string calldata reason) external pure returns (string memory);
```

**Example Implementations:**

1. **SingleOraclePolicy**
   ```solidity
   function canFinalize(address caller) external view returns (bool) {
       return caller == trustedOracle;
   }
   ```

2. **MultiOraclePolicy**
   ```solidity
   // Require 2-of-3 oracle consensus
   function canFinalize(address caller) external view returns (bool) {
       return oracleVotes[currentTaskId] >= 2;
   }
   ```

3. **DAOVotePolicy**
   ```solidity
   // Verification requires governance vote
   function canFinalize(address caller) external view returns (bool) {
       return proposal[taskId].approved && proposal[taskId].executed;
   }
   ```

**Use Case:** Decentralize trust beyond a single oracle address.

---
## Resources

- Current Implementation: [../contracts/](../contracts/)
- Testing Guide: [../test/README.md](../test/README.md)
- Main README: [../README.md](../README.md)

---

## Contributing

To add new interface templates:

1. Define interface in `templates/IYourFeature.sol`
2. Document in this README
3. Provide example implementation
4. Write tests for interface compliance

---

## License
MIT License - See [LICENSE](../../../LICENSE)
