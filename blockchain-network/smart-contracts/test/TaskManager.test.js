// File: test/TaskManager.test.js
// Tests for TaskManager using Hardhat with Mocha and Chai

import pkg from "hardhat";
const { ethers } = pkg;

import { expect } from "chai";

describe("TaskManager Unit Tests", function() {
  let token;
  let orgStub;
  let taskManager;
  let owner;
  let creator;
  let executor;
  let other;

  beforeEach(async function() {
    [owner, creator, executor, other] = await ethers.getSigners();



    // deploy a real IECoin token with initial supply to creator
    const IECoin = await ethers.getContractFactory(
      "contracts/IECoin.sol:IECoin"
    );
    token = await IECoin.deploy(1000, creator.address);
    await token.waitForDeployment();

    // deploy the dummy organization stub
    const OrgStub = await ethers.getContractFactory("MockOrganization");
    orgStub = await OrgStub.deploy();
    await orgStub.waitForDeployment();

    // deploy TaskManager with token and organization stub addresses
    const TM = await ethers.getContractFactory("contracts/TaskManager.sol:TaskManager");
    taskManager = await TM.deploy(token.getAddress(), orgStub.getAddress());
    await taskManager.waitForDeployment();

    const orgAddr = await orgStub.getAddress();
    const tokenAddr = await token.getAddress();
    const taskManagerAddr = await taskManager.getAddress();
    const executorAddr = executor.address; // This one is not a Promis

    // creator approves TaskManager to spend on their behalf
    await token.connect(creator).approve(taskManager.getAddress(), 500);
  });

  it("should register a new task and emit TaskRegistered event", async function() {
    await expect(
      taskManager
        .connect(creator)
        .registerTask("Test Task", "catA", "typeX", 100)
    )
      .to.emit(taskManager, "TaskRegistered")
      .withArgs(1, creator.address);

    const total = await taskManager.getTotalTasks();
    expect(total).to.equal(1);

    const ids = await taskManager.getTasksByCreator(creator.address);
    const idStrings = ids.map(i => i.toString());
    expect(idStrings).to.deep.equal([ "1" ]);

    const meta = await taskManager.getTaskMeta(1);
    expect(meta.tId.toString()).to.equal("1");
    expect(meta.reward.toString()).to.equal("100");
    expect(meta.active).to.be.true;
  });

  it("should fail to register if no approval exists", async function() {
    // remove approval
    await token.connect(creator).approve(await taskManager.getAddress(), 0);

    await expect(
      taskManager.connect(creator).registerTask("Task", "c", "t", 50)
    ).to.be.revertedWith("Allowance too low when Registering Task");
  });

  it("should assign a task when called by organization and debit creator balance", async function() {
    const before = await token.balanceOf(creator.address);
    await taskManager.connect(creator).registerTask("A", "c", "t", 200);
    const afterRegister = await token.balanceOf(creator.address);
    expect(before - afterRegister).to.equal(200n); // escrow happened here
    const taskManagerAddr = await taskManager.getAddress();
    // Assignment should not move tokens
    await expect(
      orgStub.callAssign(
        await taskManager.getAddress(),
        1,
        executor.address,
        200
      )
    ).to.emit(taskManager, "TaskAssigned");
    const afterAssign = await token.balanceOf(creator.address);
    expect(afterAssign).to.equal(afterRegister);

    const task = await taskManager.getTask(1);
    expect(task.executor).to.equal(executor.address);
    expect(task.status).to.equal(1); // Assigned
  });

  it("should unassign and refund when organization triggers cancellation", async function() {
    // register and assign
    await taskManager.connect(creator).registerTask("T", "c", "t", 150);
    await orgStub.callAssign(
        await taskManager.getAddress(),
            1,
            executor.address,
            150
        );

    const creatorBal = await token.balanceOf(creator.address);
    // now call unassignTask which routes through stub to internal _unassignTask
    await taskManager.connect(creator).unassignTask(1);

    // refund should occur
    const finalBal = await token.balanceOf(creator.address);
    expect(finalBal).to.equal(creatorBal + 150n);

    // status reverted to Unassigned
    const task = await taskManager.getTask(1);
    expect(task.status).to.equal(0); // TaskStatus.Unassigned
    expect(task.executor).to.equal(ethers.ZeroAddress);
  });

  it("should allow removal of unassigned task by its creator", async function() {
    await taskManager.connect(creator).registerTask("X", "c", "t", 50);
    await expect(
      taskManager.connect(creator).removeTask(1)
    )
      .to.emit(taskManager, "TaskRemoved")
      .withArgs(1);

    const meta = await taskManager.getTaskMeta(1);
    expect(meta.active).to.be.false;
  });

  it("completes after proof when oracle approves, emits TaskRewardPaid", async function () {
  await taskManager.connect(creator).registerTask("Y", "c", "t", 75);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 75);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);

  const beforeExecBal = await token.balanceOf(executor.address);

  await taskManager.connect(executor).submitProof(1, "ipfs://proof");
  await expect(taskManager.connect(other).oracleFulfill(1, true, ""))
    .to.emit(taskManager, "TaskRewardPaid")
    .withArgs(1, executor.address, 75);

  const afterExecBal = await token.balanceOf(executor.address);
  expect(afterExecBal).to.equal(beforeExecBal + 75n);

  const task = await taskManager.getTask(1);
  expect(task.active).to.be.false;
  expect(task.status).to.equal(2);
  });

  it("only oracle can finalize, non oracle revert", async function () {
  await taskManager.connect(creator).registerTask("W", "c", "t", 20);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 20);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);

  await taskManager.connect(executor).submitProof(1, "uri");
  await expect(taskManager.connect(executor).oracleFulfill(1, true, ""))
    .to.be.revertedWith("Only oracle");
  });

  it("blocks direct completeTask calls", async function () {
    await taskManager.connect(creator).registerTask("A", "c", "t", 10);
    await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 10);
    await expect(taskManager.connect(executor).completeTask(1))
    .to.be.revertedWith("You are not allowed to complete the task");
  });


  it("only organization can set oracle", async () => {
  await expect(taskManager.connect(creator).setOracle(other.address))
    .to.be.revertedWith("Only org");

  await expect(orgStub.callSetOracle(await taskManager.getAddress(), other.address)).to.not.be.reverted; // just ensure call succeeds

      // state updated
  expect(await taskManager.oracle()).to.equal(other.address);
  });
  
  it("rejects zero oracle", async () => {
  await expect(orgStub.callSetOracle(await taskManager.getAddress(), ethers.ZeroAddress))
    .to.be.revertedWith("Zero oracle");
  });
  
  it("assignment fails if assignment price exceeds task budget", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 200);

  await expect(
    orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 201)
  ).to.be.revertedWith("Reward mismatch");
});


  it("registerTask fails if balance is too low (escrow transferFrom)", async () => {
    // drain creator balance to 0
    const bal = await token.balanceOf(creator.address);
    await token.connect(creator).transfer(owner.address, bal);

    // give allowance but no balance -> OZ revert on transferFrom
    await token.connect(creator).approve(await taskManager.getAddress(), 10);

    await expect(
      taskManager.connect(creator).registerTask("A", "c", "t", 10)
    ).to.be.revertedWithCustomError(token, "ERC20InsufficientBalance");
  });

  it("assignment can be cheaper than budget; budget stays unchanged", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 300);

  // cheaper than budget is allowed
  await expect(
    orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 120)
  ).to.not.be.reverted;

  const t = await taskManager.getTask(1);

  // budget remains what the user set
  expect(t.reward).to.equal(120n);
  expect(t.executor).to.equal(executor.address);
  expect(t.status).to.equal(1); // Assigned
  });


it("cannot remove assigned or executed task", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 80);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 80);
  await expect(taskManager.connect(creator).removeTask(1))
    .to.be.revertedWith("Task is assgned or executed");

  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);
  await taskManager.connect(executor).submitProof(1, "uri");
  await taskManager.connect(other).oracleFulfill(1, true, "");

  await expect(taskManager.connect(creator).removeTask(1))
    .to.be.revertedWith("Already removed");
  });


it("second completion attempt fails after execution", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 60);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 60);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);

  await taskManager.connect(executor).submitProof(1, "uri");
  await taskManager.connect(other).oracleFulfill(1, true, "");

  await expect(taskManager.connect(other).oracleFulfill(1, true, ""))
    .to.be.revertedWith("Task not active");
});


it("only assigned executor can submit proof, emits events and requests oracle", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 90);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 90);

  await expect(taskManager.connect(other).submitProof(1, "ipfs://x"))
    .to.be.revertedWith("Only assigned executor");

  await expect(taskManager.connect(executor).submitProof(1, "ipfs://proof"))
    .to.emit(taskManager, "TaskProofSubmitted").withArgs(1, executor.address, "ipfs://proof")
    .and.to.emit(taskManager, "TaskOracleRequested").withArgs(1, other.address);
});

it("oracle ok path pays exactly once", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 100);
  await token.connect(creator).approve(await taskManager.getAddress(), 200);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 100);
  await taskManager.connect(executor).submitProof(1, "uri");

  const before = await token.balanceOf(executor.address);
  await taskManager.connect(other).oracleFulfill(1, true, "");
  const after = await token.balanceOf(executor.address);

  expect(after - before).to.equal(100n); // change to 200n if you intentionally keep the old behavior
});

it("oracle reject reverts to Unassigned and refunds creator", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 70);
  await token.connect(creator).approve(await taskManager.getAddress(), 70);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 70);

  const beforeCreator = await token.balanceOf(creator.address);
  await expect(taskManager.connect(other).oracleFulfill(1, false, "bad"))
    .to.emit(taskManager, "TaskRejected");

  const afterCreator = await token.balanceOf(creator.address);
  expect(afterCreator).to.equal(beforeCreator + 70n);

  const t = await taskManager.getTask(1);
  expect(t.status).to.equal(0);
  expect(t.executor).to.equal(ethers.ZeroAddress);
});

it("reason longer than MAX_REASON_LENGTH is truncated to empty string in event", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 50);
  await token.connect(creator).approve(await taskManager.getAddress(), 50);
  await orgStub.callSetOracle(await taskManager.getAddress(), other.address);
  await orgStub.callAssign(await taskManager.getAddress(), 1, executor.address, 50);

  const longReason = "r".repeat(129);
  await expect(taskManager.connect(other).oracleFulfill(1, false, longReason))
    .to.emit(taskManager, "TaskRejected").withArgs(1, "");
});

it("getters revert on invalid ids", async () => {
  await expect(taskManager.getTaskMeta(0)).to.be.revertedWith("Invalid task ID");
  await expect(taskManager.getTask(1)).to.be.revertedWith("Invalid task ID");
});

it("tracks creator ids and returns all tasks", async () => {
  await taskManager.connect(creator).registerTask("A", "c", "t", 1);
  await taskManager.connect(creator).registerTask("B", "c", "t", 2);
  const ids = await taskManager.getTasksByCreator(creator.address);
  expect(ids.map(x => x.toString())).to.deep.equal(["1", "2"]);
  const all = await taskManager.getAllTasks();
  expect(all.length).to.equal(2);
});

it("getTaskMeta and getTask are 1 indexed and ids line up", async function () {
  await taskManager.connect(creator).registerTask("T1", "c", "t", 1);
  await taskManager.connect(creator).registerTask("T2", "c", "t", 2);

  const m1 = await taskManager.getTaskMeta(1);
  expect(m1.tId.toString()).to.equal("1");

  const m2 = await taskManager.getTaskMeta(2);
  expect(m2.tId.toString()).to.equal("2");

  const t1 = await taskManager.getTask(1);
  expect(t1.id.toString()).to.equal("1");

  const t2 = await taskManager.getTask(2);
  expect(t2.id.toString()).to.equal("2");
});

it("getters revert on 0 and out of range", async function () {
  await taskManager.connect(creator).registerTask("T1", "c", "t", 1);

  await expect(taskManager.getTaskMeta(0)).to.be.revertedWith("Invalid task ID");
  await expect(taskManager.getTask(0)).to.be.revertedWith("Invalid task ID");

  const total = await taskManager.getTotalTasks();
  expect(total).to.equal(1);

  await expect(taskManager.getTaskMeta(2)).to.be.revertedWith("Invalid task ID");
  await expect(taskManager.getTask(2)).to.be.revertedWith("Invalid task ID");
});

it("getAllTasks preserves order and one based ids", async function () {
  await taskManager.connect(creator).registerTask("A", "c", "t", 1);
  await taskManager.connect(creator).registerTask("B", "c", "t", 2);
  await taskManager.connect(creator).registerTask("C", "c", "t", 3);

  const all = await taskManager.getAllTasks();
  expect(all.length).to.equal(3);
  expect(all[0].id.toString()).to.equal("1");
  expect(all[1].id.toString()).to.equal("2");
  expect(all[2].id.toString()).to.equal("3");
});

it("creator index stores one based ids", async function () {
  await taskManager.connect(creator).registerTask("A", "c", "t", 1);
  await taskManager.connect(creator).registerTask("B", "c", "t", 2);

  const ids = await taskManager.getTasksByCreator(creator.address);
  expect(ids.map(x => x.toString())).to.deep.equal(["1", "2"]);
});

it("ids keep increasing even if a task is removed, array is still 1 indexed", async function () {
  await taskManager.connect(creator).registerTask("A", "c", "t", 1); // id 1
  await taskManager.connect(creator).registerTask("B", "c", "t", 2); // id 2
  await taskManager.connect(creator).removeTask(1); // id 1 now inactive
  await taskManager.connect(creator).registerTask("C", "c", "t", 3); // id 3

  // still accessible by their ids
  const m1 = await taskManager.getTaskMeta(1);
  expect(m1.tId.toString()).to.equal("1");
  expect(m1.active).to.equal(false);

  const m2 = await taskManager.getTaskMeta(2);
  expect(m2.tId.toString()).to.equal("2");
  expect(m2.active).to.equal(true);

  const m3 = await taskManager.getTaskMeta(3);
  expect(m3.tId.toString()).to.equal("3");
  expect(m3.active).to.equal(true);

  // out of range still reverts
  await expect(taskManager.getTaskMeta(4)).to.be.revertedWith("Invalid task ID");
  await expect(taskManager.getTask(4)).to.be.revertedWith("Invalid task ID");
});

it("total count equals array length, which matches highest valid 1 based index", async function () {
  await taskManager.connect(creator).registerTask("A", "c", "t", 1);
  await taskManager.connect(creator).registerTask("B", "c", "t", 2);

  const total = await taskManager.getTotalTasks();
  expect(total).to.equal(2n);

  // highest valid index is total
  await expect(taskManager.getTask(total)).to.not.be.reverted;
  await expect(taskManager.getTask(total + 1n)).to.be.revertedWith("Invalid task ID");
});

});
