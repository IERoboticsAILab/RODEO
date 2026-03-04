import pkg from "hardhat";
const { ethers } = pkg;

import { expect } from "chai";


describe("Organization.sol Unit Tests", function () {
  let deployer, user, robot, oracle, org, sm, tm, iec;
  let orgAddr, tokenAddr;

  beforeEach(async function () {
    [deployer, user, robot, oracle] = await ethers.getSigners();

    const IECoin = await ethers.getContractFactory("contracts/IECoin.sol:IECoin");
    iec = await IECoin.deploy(ethers.parseEther("10000"), deployer.address);
    await iec.waitForDeployment();
    tokenAddr = await iec.getAddress();

    const Organization = await ethers.getContractFactory("contracts/Organization.sol:Organization");
    org = await Organization.deploy(tokenAddr);
    await org.waitForDeployment();
    orgAddr = await org.getAddress();

    const ServiceManager = await ethers.getContractFactory("contracts/ServiceManager.sol:ServiceManager");
    sm = await ServiceManager.deploy(orgAddr);
    await sm.waitForDeployment();

    const TaskManager = await ethers.getContractFactory("contracts/TaskManager.sol:TaskManager");
    tm = await TaskManager.deploy(tokenAddr, orgAddr);
    await tm.waitForDeployment();

    await org.setTaskManager(await tm.getAddress());
    await org.setServiceManager(await sm.getAddress());

    // set oracle for proof workflow
    await org.setOracle(oracle.address);

    // fund org and approve TaskManager through deposit
    await iec.connect(deployer).approve(orgAddr, 1000);
    await org.deposit(1000);
  });

  describe("Access Control", function () {
    it("should only allow owner to call registerTask", async function () {
      await expect(
        org.connect(user).registerTask("desc", "cat", "type", 50)
      ).to.be.reverted;
    });

    it("should only allow owner to call registerService", async function () {
      await expect(
        org.connect(user).registerService("n", "d", "c", "t", 10, 1)
      ).to.be.reverted;
    });

    it("should only allow owner to remove task or service", async function () {
      await org.registerTask("desc", "c", "t", 100);
      await org.registerService("n", "d", "c", "t", 90, 2);
      await expect(org.connect(user).removeTask(1)).to.be.reverted;
      await expect(org.connect(user).removeService(1)).to.be.reverted;
    });
  });

  describe("Assignment Logic", function () {
    it("assignTask chooses best match by price", async function () {
      await sm.connect(robot).registerService("svc1", "d", "catX", "typeX", 90, 0);
      await sm.connect(robot).registerService("svc2", "d", "catX", "typeX", 70, 0);
      await org.registerTask("t", "catX", "typeX", 100);

      const task = await tm.getTask(1);
      expect(task.executor).to.equal(robot.address);
      expect(task.status).to.equal(1);
    });

    it("tryAssignTaskForService picks highest reward matching task", async function () {
      await org.registerTask("low", "catY", "typeY", 50);
      await org.registerTask("high", "catY", "typeY", 120);

      const svcTx = await sm.connect(robot).registerService("svc", "d", "catY", "typeY", 40, 0);
      await svcTx.wait();

      const task = await tm.getTask(2);
      expect(task.executor).to.equal(robot.address);
    });

    it("no assignment occurs if no match", async function () {
      await org.registerTask("desc", "catA", "typeA", 100);
      await sm.connect(robot).registerService("svc", "desc", "catB", "typeB", 20, 0);
      const task = await tm.getTask(1);
      expect(task.status).to.equal(0);
    });
  });

  describe("Unassigning and cancellation", function () {
    it("unassignTask reassigns service to another task if available", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catChain", "typeChain", 30, 0);
      await org.registerTask("first", "catChain", "typeChain", 50);
      await org.registerTask("second", "catChain", "typeChain", 50);

      await org.unassignTask(1);

      const task2 = await tm.getTask(2);
      expect(task2.status).to.equal(1);
      expect(task2.executor).to.equal(robot.address);
    });

    it("removeTask reverts if assigned", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catD", "typeD", 30, 0);
      await org.registerTask("desc", "catD", "typeD", 50);
      await expect(org.removeTask(1)).to.be.revertedWith("Task assigned! Please unassing the task.");
    });

    it("removeService reverts if busy", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catE", "typeE", 30, 0);
      await org.registerTask("desc", "catE", "typeE", 50);
      await expect(org.removeService(1)).to.be.revertedWith("Service busy! Please unassing the task asociated to this service.");
    });
  });

  describe("Task completion through oracle", function () {
    it("completes task and clears mapping", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catF", "typeF", 20, 0);
      await org.registerTask("job", "catF", "typeF", 20);

      const before = await iec.balanceOf(robot.address);

      // finish through proof and oracle
      await tm.connect(robot).submitProof(1, "ipfs://proofF");
      await tm.connect(oracle).oracleFulfill(1, true, "");

      const after = await iec.balanceOf(robot.address);
      expect(after - before).to.equal(20n);

      const service = await sm.getService(1);
      expect(service.busy).to.be.false;
    });
  });

  describe("Token and deposit logic", function () {
    it("deposit approves token allowance for TaskManager", async function () {
      const allowance = await iec.allowance(orgAddr, await tm.getAddress());
      expect(allowance).to.equal(1000n);
    });

    it("deposit fails if transferFrom fails", async function () {
      await expect(org.connect(user).deposit(500)).to.be.reverted;
    });
  });

  describe("Mapping and Cleanup", function () {
    it("correctly maps taskToService and serviceToTask, and clears after completion", async function () {
      await sm.connect(robot).registerService("s1", "desc", "catZ", "typeZ", 20, 0);
      await sm.connect(robot).registerService("s2", "desc", "catZ", "typeZ", 30, 0);
      await sm.connect(robot).registerService("s3", "desc", "catZ", "typeZ", 25, 0);

      await org.registerTask("t1", "catZ", "typeZ", 50);
      await org.registerTask("t2", "catZ", "typeZ", 40);
      await org.registerTask("t3", "catZ", "typeZ", 30);

      expect(await org.taskToService(1)).to.be.gt(0);
      expect(await org.taskToService(2)).to.be.gt(0);
      expect(await org.taskToService(3)).to.be.gt(0);

      const serviceId1 = await org.taskToService(1);
      const taskIdFromService1 = await org.serviceToTask(serviceId1);
      expect(taskIdFromService1).to.equal(1);

      // finish task 1 through oracle
      await tm.connect(robot).submitProof(1, "ipfs://proofZ1");
      await tm.connect(oracle).oracleFulfill(1, true, "");

      expect(await org.taskToService(1)).to.equal(0);
      expect(await org.serviceToTask(serviceId1)).to.equal(0);
    });

    it("reverts when removing assigned tasks or busy services", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catQ", "typeQ", 10, 0);
      await org.registerTask("work", "catQ", "typeQ", 20);

      const task = await tm.getTask(1);
      expect(task.status).to.equal(1);
      const service = await sm.getService(1);
      expect(service.busy).to.be.true;

      await expect(org.removeTask(1)).to.be.revertedWith("Task assigned! Please unassing the task.");
      await expect(org.removeService(1)).to.be.revertedWith("Service busy! Please unassing the task asociated to this service.");
    });

    it("unassigning a task reassigns the service if other tasks match", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catChain", "typeChain", 40, 0);
      await org.registerTask("first", "catChain", "typeChain", 40);
      await org.registerTask("second", "catChain", "typeChain", 40);

      await org.unassignTask(1);

      const task1 = await tm.getTask(1);
      const task2 = await tm.getTask(2);
      expect(task1.executor).to.equal(ethers.ZeroAddress);
      expect(task1.status).to.equal(0);
      expect(task2.executor).to.equal(robot.address);
      expect(task2.status).to.equal(1);

      const reassignedSvc = await org.taskToService(2);
      expect(reassignedSvc).to.equal(1);
    });

    it("assigns the cheapest available matching service to each task", async function () {
      await sm.connect(robot).registerService("svcHigh", "desc", "catOpt", "typeOpt", 80, 0);
      await sm.connect(robot).registerService("svcLow", "desc", "catOpt", "typeOpt", 40, 0);
      await sm.connect(robot).registerService("svcMid", "desc", "catOpt", "typeOpt", 60, 0);

      await org.registerTask("matchCheapest", "catOpt", "typeOpt", 100);

      const task = await tm.getTask(1);
      expect(task.status).to.equal(1);

      const assignedServiceId = await org.taskToService(1);
      const assignedService = await sm.getService(assignedServiceId);
      expect(assignedService.price).to.equal(40);

      const s1 = await sm.getService(1);
      const s2 = await sm.getService(2);
      const s3 = await sm.getService(3);
      expect([s1.busy, s2.busy, s3.busy].filter(b => b).length).to.equal(1);
      expect(s2.busy).to.be.true;
    });

    it("assigns each task to the cheapest matching service when multiple exist", async function () {
      await sm.connect(robot).registerService("svcA", "desc", "catMulti", "typeMulti", 70, 0);
      await sm.connect(robot).registerService("svcB", "desc", "catMulti", "typeMulti", 40, 0);
      await sm.connect(robot).registerService("svcC", "desc", "catMulti", "typeMulti", 50, 0);

      await org.registerTask("task1", "catMulti", "typeMulti", 60);
      await org.registerTask("task2", "catMulti", "typeMulti", 75);
      await org.registerTask("task3", "catMulti", "typeMulti", 100);

      const assignedSvc1 = await org.taskToService(1);
      const assignedSvc2 = await org.taskToService(2);
      const assignedSvc3 = await org.taskToService(3);

      const s1 = await sm.getService(assignedSvc1);
      const s2 = await sm.getService(assignedSvc2);
      const s3 = await sm.getService(assignedSvc3);

      expect(s1.price).to.equal(40);
      expect(s2.price).to.equal(50);
      expect(s3.price).to.equal(70);
    });

    it("assigns best available services to existing tasks when services are registered later", async function () {
      await org.registerTask("taskA", "catDelay", "typeDelay", 60);
      await org.registerTask("taskB", "catDelay", "typeDelay", 80);
      await org.registerTask("taskC", "catDelay", "typeDelay", 90);

      const task1 = await tm.getTask(1);
      const task2 = await tm.getTask(2);
      const task3 = await tm.getTask(3);
      expect(task1.status).to.equal(0);
      expect(task2.status).to.equal(0);
      expect(task3.status).to.equal(0);

      await sm.connect(robot).registerService("delayedC", "d", "catDelay", "typeDelay", 85, 0);
      await sm.connect(robot).registerService("delayedB", "d", "catDelay", "typeDelay", 55, 0);
      await sm.connect(robot).registerService("delayedA", "d", "catDelay", "typeDelay", 45, 0);

      const svcId1 = await org.taskToService(1);
      const svcId2 = await org.taskToService(2);
      const svcId3 = await org.taskToService(3);

      const svc1 = await sm.getService(svcId1);
      const svc2 = await sm.getService(svcId2);
      const svc3 = await sm.getService(svcId3);

      expect(svc1.price).to.equal(45);
      expect(svc2.price).to.equal(55);
      expect(svc3.price).to.equal(85);
    });

    it("onTaskComplete triggers reassignment of service to another matching task", async function () {
      await sm.connect(robot).registerService("svc", "desc", "catDone", "typeDone", 50, 0);
      await org.registerTask("taskA", "catDone", "typeDone", 50);
      await org.registerTask("taskB", "catDone", "typeDone", 50);

      const taskA = await tm.getTask(1);
      expect(taskA.executor).to.equal(robot.address);
      expect(taskA.status).to.equal(1);

      await tm.connect(robot).submitProof(1, "ipfs://proofDoneA");
      await tm.connect(oracle).oracleFulfill(1, true, "");

      const taskB = await tm.getTask(2);
      expect(taskB.executor).to.equal(robot.address);
      expect(taskB.status).to.equal(1);

      const mappedService = await org.taskToService(2);
      expect(mappedService).to.equal(1);
    });
  });

  describe("Org driven finish", function () {
  it("owner set as oracle approves and finishes", async function () {
    // Make the org owner the oracle, do this before finishing
    await org.setOracle(deployer.address);

    // Register matching service and task
    await sm.connect(robot).registerService("svc", "d", "catO", "typeO", 25, 0);
    await org.registerTask("job", "catO", "typeO", 25);

    // Executor submits proof
    await tm.connect(robot).submitProof(1, "ipfs://proofO");

    const before = await iec.balanceOf(robot.address);

    // Org owner acts as oracle and finalizes
    await tm.connect(deployer).oracleFulfill(1, true, "");

    const after = await iec.balanceOf(robot.address);
    expect(after - before).to.equal(25n);

    const t = await tm.getTask(1);
    expect(t.status).to.equal(2); // Executed
    expect(t.active).to.equal(false);

    const svc = await sm.getService(1);
    expect(svc.busy).to.equal(false);
    expect(await org.taskToService(1)).to.equal(0);
    expect(await org.serviceToTask(1)).to.equal(0);
  });
  });

  describe("New dApp flow tests", function () {

  it("human creates task directly, needs balance and allowance when a matching service exists", async function () {
    // Give user some tokens
    await iec.transfer(user.address, 200);
    // Robot posts a matching cheap service first
    await sm.connect(robot).registerService("r1", "d", "catH", "typeH", 100, 0);

    // No allowance yet, direct task registration should revert during onTaskRegistered
    await expect(
      tm.connect(user).registerTask("do it", "catH", "typeH", 150)
    ).to.be.reverted;

    // Approve but no balance enough
    await iec.connect(user).approve(await tm.getAddress(), 150);
    // Drain user to create insufficient balance
    await iec.connect(user).transfer(deployer.address, 200);
    await expect(
      tm.connect(user).registerTask("do it", "catH", "typeH", 150)
    ).to.be.reverted;

    // Fund again and succeed
    await iec.transfer(user.address, 200);
    await iec.connect(user).approve(await tm.getAddress(), 150);
    await expect(
      tm.connect(user).registerTask("do it", "catH", "typeH", 150)
    ).to.not.be.reverted;

    const task = await tm.getTask(1);
    expect(task.creator).to.equal(user.address);
    expect(task.executor).to.equal(robot.address);
    expect(task.status).to.equal(1);
  });

  it("human can register a task with no matches without allowance, later service registration triggers payment", async function () {
    // Fund + approve BEFORE registering (registerTask escrows immediately)
    await iec.transfer(user.address, 100);
    await iec.connect(user).approve(await tm.getAddress(), 60);
    
     // No services exist yet -> should NOT revert, but task remains unassigned
    await expect(
      tm.connect(user).registerTask("pending", "catLater", "typeLater", 60)
    ).to.not.be.reverted;

    const t0 = await tm.getTask(1);
    expect(t0.status).to.equal(0); // Unassigned
    expect(t0.executor).to.equal(ethers.ZeroAddress);

    // Register matching service, this triggers tryAssignTaskForService
    await sm.connect(robot).registerService("svc", "d", "catLater", "typeLater", 50, 0);

    const t = await tm.getTask(1);
    expect(t.status).to.equal(1);
    expect(t.executor).to.equal(robot.address);
  });

  it("only the assigned executor can submit proof, URI must be non empty", async function () {
    await sm.connect(robot).registerService("svc", "d", "catP", "typeP", 25, 0);
    await org.registerTask("job", "catP", "typeP", 25);

    await expect(tm.connect(user).submitProof(1, "ipfs://x")).to.be.revertedWith("Only assigned executor");
    await expect(tm.connect(robot).submitProof(1, "")).to.be.revertedWith("Bad URI");

    await expect(tm.connect(robot).submitProof(1, "ipfs://proofP")).to.emit(tm, "TaskProofSubmitted");
  });

  it("busy flag can be flipped only by creator or organization", async function () {
    const reg = await sm.connect(robot).registerService("svc", "d", "catB", "typeB", 10, 0);
    await reg.wait();

    // Random user cannot toggle
    await expect(sm.connect(user).setBusy(1, true)).to.be.revertedWith("Only service creators or organization can set a service as busy");

    // Creator can toggle
    await expect(sm.connect(robot).setBusy(1, true)).to.emit(sm, "ServiceBusyUpdated");
    await expect(sm.connect(robot).setBusy(1, false)).to.emit(sm, "ServiceBusyUpdated");

    // Organization can toggle too
    await expect(org.connect(deployer).setServiceBusy(1, true)).to.emit(sm, "ServiceBusyUpdated");
  });

  it("reactivating an inactive service causes assignment when a matching task exists", async function () {
    const s = await sm.connect(robot).registerService("svc", "d", "catR", "typeR", 30, 0);
    await s.wait();

    // Remove service while idle
    await sm.connect(robot).removeService(1);
    const svcRemoved = await sm.getService(1);
    expect(svcRemoved.active).to.equal(false);

    // Create a matching task
    await org.registerTask("t", "catR", "typeR", 40);

    // Reactivate by creator, ServiceManager calls organization.onServiceRegistered
    await sm.connect(robot).activateService(1);

    const task = await tm.getTask(1);
    expect(task.status).to.equal(1);
    expect(task.executor).to.equal(robot.address);
  });

  it("price equal to reward still matches", async function () {
    await sm.connect(robot).registerService("svc", "d", "catEq", "typeEq", 50, 0);
    await org.registerTask("t", "catEq", "typeEq", 50);
    const t = await tm.getTask(1);
    expect(t.status).to.equal(1);
  });

  it("organization wrapper cannot activate or remove an idle service it did not create", async function () {
    // Robot creates a service and leaves it active and idle
    await sm.connect(robot).registerService("svc", "d", "catW", "typeW", 10, 0);

    // Try to remove through org wrapper, mapping is empty so org passes its own check then hits ServiceManager require
    await expect(org.removeService(1)).to.be.revertedWith("Only creator can remove service");

    // Deactivate by robot, then org tries to activate, should revert at ServiceManager
    await sm.connect(robot).removeService(1);
    await expect(org.activateService(1)).to.be.revertedWith("Only creator can activate service");
  });

  it("late service registration assigns, but does not transfer tokens at assignment (escrow-on-register)", async function () {
    // Create task first with higher reward
    await org.registerTask("rich", "catPrice", "typePrice", 100);

    // Measure TaskManager token balance before service appears
    const tmAddr = await tm.getAddress();
    const before = await iec.balanceOf(tmAddr);

    // Register matching service with lower price
    await sm.connect(robot).registerService("svc", "d", "catPrice", "typePrice", 30, 0);

    const after = await iec.balanceOf(tmAddr);
    // Correct behavior should transfer 0 tokens at assignment, since escrow was done at task registration
    expect(after - before).to.equal(0n);

    const t = await tm.getTask(1);
    expect(t.status).to.equal(1);
    expect(t.executor).to.equal(robot.address);

  });

  it("oracle rejection refunds and frees service, then reassigns if another task matches EXPECTED TO FAIL until fix", async function () {
    // Service and two tasks
    await sm.connect(robot).registerService("svc", "d", "catRej", "typeRej", 40, 0);
    await org.registerTask("first", "catRej", "typeRej", 50);
    await org.registerTask("second", "catRej", "typeRej", 50);

    // Submit bad proof for first task
    await tm.connect(robot).submitProof(1, "ipfs://bad");
    // Set oracle
    await org.setOracle(oracle.address);

    // Oracle rejects
    await tm.connect(oracle).oracleFulfill(1, false, "not ok");

    // Task 1 should be unassigned and refunded to creator
    const t1 = await tm.getTask(1);
    expect(t1.status).to.equal(0);
    expect(t1.executor).to.equal(ethers.ZeroAddress);

    // Service should be busy again on task 2
    const t2 = await tm.getTask(2);
    expect(t2.status).to.equal(1);
    expect(t2.executor).to.equal(robot.address);
  });

  it("double oracleFulfill after success reverts the second time", async function () {
    await sm.connect(robot).registerService("svc", "d", "catDouble", "typeDouble", 20, 0);
    await org.registerTask("t", "catDouble", "typeDouble", 20);

    await tm.connect(robot).submitProof(1, "ipfs://good");
    await tm.connect(oracle).oracleFulfill(1, true, "");

    // Second call should revert since task is no longer active or assigned
    await expect(tm.connect(oracle).oracleFulfill(1, true, "")).to.be.reverted;
  });

  });

describe("Requested mixed entity scenarios", function () {

  it("Robot then human execute and get rewards", async function () {
    // Org posts two services and two tasks that do not match each other
    await org.registerService("O_S1", "d", "orgA", "typeA", 30, 2);
    await org.registerService("O_S2", "d", "orgB", "typeB", 40, 2);
    await org.registerTask("O_T1", "matchOrg", "mType", 50); // will match robot service later
    await org.registerTask("O_T2", "orgOnly", "oType", 60);

    await iec.transfer(user.address, 200);
    await iec.connect(user).approve(await tm.getAddress(), 200);

    // Human posts two services and two tasks, still no match in the system
    await sm.connect(user).registerService("H_S1", "d", "humanS", "hsType", 30, 1); // will match robot task later
    await sm.connect(user).registerService("H_S2", "d", "humanS2", "hsType2", 35, 1);
    await tm.connect(user).registerTask("H_T1", "humanT1", "htType1", 20);
    await tm.connect(user).registerTask("H_T2", "humanT2", "htType2", 25);

    // Fund robot for its own future task and approve TaskManager
    await iec.transfer(robot.address, 100);
    await iec.connect(robot).approve(await tm.getAddress(), 100);

    // Robot posts one service that matches org task O_T1
    await sm.connect(robot).registerService("R_S1", "d", "matchOrg", "mType", 50, 0);
    // After this, task 1 should be assigned to robot
    let t1 = await tm.getTask(1);
    expect(t1.status).to.equal(1);
    expect(t1.executor).to.equal(robot.address);

    // Robot posts one task that matches human service H_S1
    await tm.connect(robot).registerTask("R_T1", "humanS", "hsType", 30); // will match H_S1
    const t5 = await tm.getTask(5); // ids so far: 1..4 existed, this is 5
    expect(t5.status).to.equal(1);
    expect(t5.executor).to.equal(user.address);

    // First the robot executes org task and gets reward
    const robotBefore = await iec.balanceOf(robot.address);
    await tm.connect(robot).submitProof(1, "ipfs://proof_robot_execs_org_task");
    await tm.connect(oracle).oracleFulfill(1, true, "");
    const robotAfter = await iec.balanceOf(robot.address);
    expect(robotAfter - robotBefore).to.equal(50n);

    // Then the human executes robot task and gets reward
    const humanBefore = await iec.balanceOf(user.address);
    await tm.connect(user).submitProof(5, "ipfs://proof_human_execs_robot_task");
    await tm.connect(oracle).oracleFulfill(5, true, "");
    const humanAfter = await iec.balanceOf(user.address);
    expect(humanAfter - humanBefore).to.equal(30n);

    // Both services should be free again
    const svcRobot = await sm.getService(3); // R_S1 is third service overall
    expect(svcRobot.busy).to.equal(false);
    const svcHuman = await sm.getService(1); // H_S1 was first human service, overall index 1 after two org services
    // Careful with indexes: services are global, order was O_S1(1), O_S2(2), H_S1(3), H_S2(4), R_S1(5)
    // So correct checks:
    const s5 = await sm.getService(5); // R_S1
    expect(s5.busy).to.equal(false);
    const s3 = await sm.getService(3); // H_S1
    expect(s3.busy).to.equal(false);
  });

  it("Human then organization execute and get rewards", async function () {
       // Fund robot for its tasks, approve before org service appears
    await iec.transfer(robot.address, 100);
    await iec.connect(robot).approve(await tm.getAddress(), 100);
    
    // Robot posts two services and two tasks that do not match each other
    await sm.connect(robot).registerService("R_S1", "d", "rA", "rtA", 22, 0);
    await sm.connect(robot).registerService("R_S2", "d", "rB", "rtB", 33, 0);
    await tm.connect(robot).registerTask("R_T1", "matchOrgSvc", "mos", 40); // will match org service later
    await tm.connect(robot).registerTask("R_T2", "rOnly", "rOnlyT", 55);

    await iec.transfer(user.address, 200);
    await iec.connect(user).approve(await tm.getAddress(), 200);

    // Human posts two services and two tasks, still no match
    await sm.connect(user).registerService("H_S1", "d", "matchOrgTask", "mot", 35, 1); // will match org task later
    await sm.connect(user).registerService("H_S2", "d", "hB", "htB", 45, 1);
    await tm.connect(user).registerTask("H_T1", "hOnly1", "hOnlyT1", 20);
    await tm.connect(user).registerTask("H_T2", "hOnly2", "hOnlyT2", 25);

 

    // Organization posts one service that matches robot task R_T1
    await org.registerService("O_S_match_R_T1", "d", "matchOrgSvc", "mos", 40, 2);
    // Now task R_T1 should be assigned to Organization as executor
    const t3 = await tm.getTask(1); // third task created overall in this test
    expect(t3.status).to.equal(1);
    expect(t3.executor).to.equal(await org.getAddress());

    // Organization posts one task that matches human service H_S1
    await org.registerTask("O_T_match_H_S1", "matchOrgTask", "mot", 35);
    const t6 = await tm.getTask(5); // ids moved forward, this is sixth
    expect(t6.status).to.equal(1);
    expect(t6.executor).to.equal(user.address);

    // First the human executes the org task and gets reward
    const humanBefore = await iec.balanceOf(user.address);
    await tm.connect(user).submitProof(5, "ipfs://proof_human_execs_org_task");
    await tm.connect(oracle).oracleFulfill(5, true, "");
    const humanAfter = await iec.balanceOf(user.address);
    expect(humanAfter - humanBefore).to.equal(35n);

    // Then the organization executes the robot task and gets reward
    // Requires Organization helper submitProofAsExecutor in Organization.sol
    const orgBefore = await iec.balanceOf(await org.getAddress());
    await org.submitProofAsExecutor(1, "ipfs://proof_org_execs_robot_task");
    await tm.connect(oracle).oracleFulfill(1, true, "");
    const orgAfter = await iec.balanceOf(await org.getAddress());
    expect(orgAfter - orgBefore).to.equal(40n);

    // Services should be free again
    const sOrg = await sm.getService(5); // careful with indices, service order in this test:
    // R_S1(1), R_S2(2), H_S1(3), H_S2(4), O_S_match_R_T1(5)
    const s5 = await sm.getService(3); // the org service that executed R_T1
    expect(s5.busy).to.equal(false);
    const s3 = await sm.getService(3); // H_S1 that executed O_T_match_H_S1
    expect(s3.busy).to.equal(false);
  });

});
});
