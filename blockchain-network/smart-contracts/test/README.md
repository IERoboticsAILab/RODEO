# Smart Contract Tests

Comprehensive test suite for RODEO smart contracts using Hardhat with Mocha and Chai.

## Test Structure

```
test/
├── Organization.test.js    # Integration tests (25 tests)
├── TaskManager.test.js     # Task lifecycle (16 tests)
└── ServiceManager.test.js  # Service operations (4 tests)
```

**Total: 45 tests with 100% coverage**

---

## Running Tests

### Run All Tests
```bash
# From smart-contracts/ directory
npx hardhat test
```

**Expected output:**
```
  Organization Integration Tests
    ✔ should deploy all contracts (456ms)
    ✔ should register and match task with service (312ms)
    ✔ should handle task execution and payment (287ms)
    ✔ should refund on task removal (198ms)
    ✔ should handle task unassignment (245ms)
    ✔ should handle proof submission and verification (189ms)
    ✔ should reject invalid proof (167ms)
    ... (18 more tests)

  TaskManager Unit Tests
    ✔ should register a new task (245ms)
    ✔ should escrow funds on registration (198ms)
    ✔ should fail to register if no approval exists (167ms)
    ✔ should assign task executor (167ms)
    ✔ should submit proof (134ms)
    ✔ should verify task (112ms)
    ✔ should reject proof with reason (98ms)
    ✔ should complete task and pay executor (156ms)
    ... (8 more tests)

  ServiceManager Unit Tests
    ✔ should register service (134ms)
    ✔ should update busy status (98ms)
    ✔ should remove service (87ms)
    ✔ should prevent duplicate registration (76ms)

  45 passing (4s)
```

### Run Specific Test File
```bash
npx hardhat test test/Organization.test.js
npx hardhat test test/TaskManager.test.js
npx hardhat test test/ServiceManager.test.js
```

### Run Specific Test by Name
```bash
npx hardhat test --grep "should handle task execution"
npx hardhat test --grep "escrow"
npx hardhat test --grep "oracle"
```

### Generate Coverage Report
```bash
npx hardhat coverage
```

This generates a detailed HTML report in `coverage/index.html` showing:
- Line coverage
- Branch coverage
- Function coverage
- Statement coverage

---

## Test Coverage

All contracts have 100% test coverage:

| Contract | Line Coverage | Branch Coverage | Tests |
|----------|--------------|-----------------|-------|
| Organization.sol | 100% | 100% | 25 tests |
| TaskManager.sol | 100% | 100% | 16 tests |
| ServiceManager.sol | 100% | 100% | 4 tests |
| IECoin.sol | N/A | N/A | Inherited (OpenZeppelin) |

---

## Debugging Tests

### View Test Output
```bash
npx hardhat test --verbose
```

### Debug Specific Test
```bash
npx hardhat test --grep "should fail" --verbose
```

### Check Gas Usage
```bash
REPORT_GAS=true npx hardhat test
```

### Run Tests in  Watch Mode
```bash
npx hardhat watch test
```

---



## Adding New Tests

### 1. Create Test File
```javascript
// test/NewContract.test.js
import { expect } from "chai";
import { ethers } from "hardhat";

describe("NewContract", function() {
  let contract;
  let owner, user;
  
  beforeEach(async function() {
    [owner, user] = await ethers.getSigners();
    const Contract = await ethers.getContractFactory("NewContract");
    contract = await Contract.deploy();
  });
  
  it("should do something", async function() {
    // Test implementation
  });
});
```

### 2. Run New Tests
```bash
npx hardhat test test/NewContract.test.js
```

### 3. Check Coverage
```bash
npx hardhat coverage
```

---

## Test Accounts

Hardhat provides test accounts with pre-funded ETH:

```javascript
const [
  owner,         // 0x70997970C51812dc3A010C7d01b50e0d17dc79C8
  creator,       // 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
  executor,      // 0x90F79bf6EB2c4f870365E785982E1f101E93b906
  oracle,        // 0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65
  robot1,        // 0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc
  robot2,        // 0x976EA74026E726554dB657fA54763abd0C3a0aa9
  // ... 14 more accounts
] = await ethers.getSigners();
```

Each account starts with **10,000 ETH** on Hardhat network.

---

## License
MIT License - See [LICENSE](../../../LICENSE)
