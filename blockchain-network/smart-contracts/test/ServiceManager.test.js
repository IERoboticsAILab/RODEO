// File: test/ServiceManager.test.js

import pkg from "hardhat";
const { ethers } = pkg;

import { expect } from "chai";

describe("ServiceManager Unit Tests", function () {
  let serviceManager;
  let mockOrg;
  let owner;
  let provider;
  let other;

  beforeEach(async function () {
    [owner, provider, other] = await ethers.getSigners();

    // Deploy MockOrganization as the receiver of service events
    const MockOrgFactory = await ethers.getContractFactory("MockOrganization");
    mockOrg = await MockOrgFactory.deploy();
    await mockOrg.waitForDeployment();

    // Deploy ServiceManager with the mock organization address
    const ServiceManager = await ethers.getContractFactory("contracts/ServiceManager.sol:ServiceManager");
    serviceManager = await ServiceManager.deploy(await mockOrg.getAddress());
    await serviceManager.waitForDeployment();
  });

  it("should register a new service and emit ServiceRegistered", async function () {
    await expect(
      serviceManager
        .connect(provider)
        .registerService("ServiceA", "Desc", "cat1", "type1", 100, 0) // ProviderType.Robot
    )
      .to.emit(serviceManager, "ServiceRegistered")
      .withArgs(1, provider.address);

    const service = await serviceManager.getService(1);
    expect(service.name).to.equal("ServiceA");
    expect(service.active).to.be.true;
    expect(service.busy).to.be.false;
    expect(service.providerType).to.equal(0);

    const count = await serviceManager.getServiceCount();
    expect(count).to.equal(1);
  });

  it("should allow creator to remove an inactive service", async function () {
    await serviceManager
      .connect(provider)
      .registerService("S", "Desc", "cat", "type", 50, 1);

    await expect(
      serviceManager.connect(provider).removeService(1)
    )
      .to.emit(serviceManager, "ServiceRemoved")
      .withArgs(1);

    const meta = await serviceManager.getServiceMeta(1);
    expect(meta.active).to.be.false;
    expect(meta.busy).to.be.false;
  });

  it("should not remove a busy service", async function () {
    await serviceManager
      .connect(provider)
      .registerService("BusyService", "Desc", "cat", "type", 50, 1);

    await serviceManager
      .connect(provider)
      .setBusy(1, true); // Set as org

    await expect(
      serviceManager.connect(provider).removeService(1)
    ).to.be.revertedWith("Cant remove busy service. First unassing task");
  });

  it("should allow creator to reactivate a previously removed service", async function () {
    await serviceManager
      .connect(provider)
      .registerService("ReActivatable", "Desc", "cat", "type", 70, 2);

    await serviceManager.connect(provider).removeService(1);

    await expect(
      serviceManager.connect(provider).activateService(1)
    )
      .to.emit(serviceManager, "ServiceRegistered")
      .withArgs(1, provider.address);

    const service = await serviceManager.getService(1);
    expect(service.active).to.be.true;
    expect(service.busy).to.be.false;
  });

  it("should reject reactivation of a busy service", async function () {
    await serviceManager
      .connect(provider)
      .registerService("Busy", "Desc", "cat", "type", 80, 0);

    await mockOrg.callSetBusy( await serviceManager.getAddress(), 1, true);

    await expect(
      serviceManager.connect(provider).activateService(1)
    ).to.be.revertedWith("Already active or service is busy");
  });


  it("should return services by creator", async function () {
    await serviceManager
      .connect(provider)
      .registerService("S1", "Desc", "cat", "type", 20, 0);
    await serviceManager
      .connect(provider)
      .registerService("S2", "Desc", "cat", "type", 30, 0);

    const ids = await serviceManager.getServicesByCreator(provider.address);
    expect(ids.map(i => i.toString())).to.deep.equal(["1", "2"]);
  });

  it("should get all registered services", async function () {
    await serviceManager
      .connect(provider)
      .registerService("One", "Desc", "cat", "type", 10, 0);
    await serviceManager
      .connect(provider)
      .registerService("Two", "Desc", "cat", "type", 15, 1);

    const all = await serviceManager.getAllServices();
    expect(all.length).to.equal(2);
    expect(all[0].name).to.equal("One");
    expect(all[1].name).to.equal("Two");
  });

  it("only creator or org can setBusy", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "cat", "type", 10, 0);

  await expect(
    serviceManager.connect(other).setBusy(1, true)
  ).to.be.revertedWith(
    "Only service creators or organization can set a service as busy"
  );

  // creator can set
  await expect(serviceManager.connect(provider).setBusy(1, true))
    .to.emit(serviceManager, "ServiceBusyUpdated")
    .withArgs(1, true);

  // org can set
  await expect(
    mockOrg.callSetBusy(await serviceManager.getAddress(), 1, false)
  ).to.not.be.reverted;
  });

  it("remove and activate are creator only", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "cat", "type", 10, 0);

  await expect(serviceManager.connect(other).removeService(1))
    .to.be.revertedWith("Only creator can remove service");

  await serviceManager.connect(provider).removeService(1);
  await expect(serviceManager.connect(other).activateService(1))
    .to.be.revertedWith("Only creator can activate service");
  });

  it("guards on invalid index, zero and out of range", async function () {
  await expect(serviceManager.getService(0)).to.be.revertedWith("Invalid index");
  await expect(serviceManager.getServiceMeta(0)).to.be.revertedWith("Invalid index");
  await expect(serviceManager.removeService(0)).to.be.revertedWith("Invalid index");
  await expect(serviceManager.activateService(0)).to.be.revertedWith("Invalid index");

  await expect(serviceManager.getService(1)).to.be.revertedWith("Invalid index"); // empty set
  });

  it("activate fails when already active", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "cat", "type", 10, 0);

  await expect(serviceManager.connect(provider).activateService(1))
    .to.be.revertedWith("Already active or service is busy");
  });

  it("remove fails when already removed", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "cat", "type", 10, 0);

  await serviceManager.connect(provider).removeService(1);
  await expect(serviceManager.connect(provider).removeService(1))
    .to.be.revertedWith("Already removed");
  });

  it("categoryHash and serviceTypeHash are keccak of inputs", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "vision", "segmentation", 42, 0);

  const meta = await serviceManager.getServiceMeta(1);
  expect(meta.categoryHash).to.equal(ethers.id("vision"));
  expect(meta.serviceTypeHash).to.equal(ethers.id("segmentation"));
  expect(meta.price).to.equal(42);
  expect(meta.creator).to.equal(provider.address);
  });
  
  it("ids are monotonic and not reused after removal", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "c", "t", 1, 0); // id 1
  await serviceManager.connect(provider).registerService("B", "D", "c", "t", 1, 0); // id 2
  await serviceManager.connect(provider).removeService(1);
  await serviceManager.connect(provider).registerService("C", "D", "c", "t", 1, 0); // id 3

  const s1 = await serviceManager.getService(1);
  const s2 = await serviceManager.getService(2);
  const s3 = await serviceManager.getService(3);

  expect(s1.id).to.equal(1);
  expect(s2.id).to.equal(2);
  expect(s3.id).to.equal(3);

  const count = await serviceManager.getServiceCount();
  expect(count).to.equal(3);
  });

  it("busy on active service blocks reactivation until cleared", async function () {
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "cat", "type", 10, 0);

  // org marks busy while inactive
  await mockOrg.callSetBusy(await serviceManager.getAddress(), 1, true);

  await expect(
    serviceManager.connect(provider).activateService(1)
  ).to.be.revertedWith("Already active or service is busy");

  

  // clear busy, remove service then activate works
  await mockOrg.callSetBusy(await serviceManager.getAddress(), 1, false);
  await serviceManager.connect(provider).removeService(1);
  await expect(
    serviceManager.connect(provider).activateService(1)
  )
    .to.emit(serviceManager, "ServiceRegistered")
    .withArgs(1, provider.address);
  });

  it("getServicesByCreator keeps ids after removal", async function () {
  await serviceManager.connect(provider).registerService("S1", "D", "c", "t", 1, 0);
  await serviceManager.connect(provider).registerService("S2", "D", "c", "t", 1, 0);
  await serviceManager.connect(provider).removeService(1);

  const ids = await serviceManager.getServicesByCreator(provider.address);
  expect(ids.map(x => x.toString())).to.deep.equal(["1", "2"]);
  });

  it("org callback fires on register and on reactivate", async function () {
  // This assumes your MockOrganization tracks counts.
  // If it does not, replace it with the mock below.
  await serviceManager
    .connect(provider)
    .registerService("S", "D", "c", "t", 1, 0);

  expect(await mockOrg.registeredCount()).to.equal(1);
  await serviceManager.connect(provider).removeService(1);
  await serviceManager.connect(provider).activateService(1);
  expect(await mockOrg.registeredCount()).to.equal(2);
  });

  it("indexes start at one for getService and getServiceMeta", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // id 1
  await serviceManager.connect(provider).registerService("B", "D", "cat", "type", 20, 1); // id 2
  await serviceManager.connect(other).registerService("C", "D", "cat", "type", 30, 2);   // id 3

  const s1 = await serviceManager.getService(1);
  expect(s1.id).to.equal(1);
  expect(s1.name).to.equal("A");

  const m1 = await serviceManager.getServiceMeta(1);
  expect(m1.sid).to.equal(1);
  expect(m1.creator).to.equal(provider.address);
  expect(m1.price).to.equal(10);

  const s2 = await serviceManager.getService(2);
  expect(s2.id).to.equal(2);
  expect(s2.name).to.equal("B");

  const m2 = await serviceManager.getServiceMeta(2);
  expect(m2.sid).to.equal(2);
  expect(m2.creator).to.equal(provider.address);
  expect(m2.price).to.equal(20);

  const s3 = await serviceManager.getService(3);
  expect(s3.id).to.equal(3);
  expect(s3.name).to.equal("C");

  const m3 = await serviceManager.getServiceMeta(3);
  expect(m3.sid).to.equal(3);
  expect(m3.creator).to.equal(other.address);
  expect(m3.price).to.equal(30);
});

it("getServiceCount and getAllServices align with one based ids", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // 1
  await serviceManager.connect(provider).registerService("B", "D", "cat", "type", 20, 1); // 2
  await serviceManager.connect(provider).registerService("C", "D", "cat", "type", 30, 2); // 3

  const count = await serviceManager.getServiceCount();
  expect(count).to.equal(3);

  const all = await serviceManager.getAllServices();
  expect(all.length).to.equal(3);
  expect(all[0].id).to.equal(1);
  expect(all[0].name).to.equal("A");
  expect(all[1].id).to.equal(2);
  expect(all[1].name).to.equal("B");
  expect(all[2].id).to.equal(3);
  expect(all[2].name).to.equal("C");
});

it("getServicesByCreator returns ids that start at one", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // 1
  await serviceManager.connect(provider).registerService("B", "D", "cat", "type", 20, 1); // 2
  await serviceManager.connect(other).registerService("C", "D", "cat", "type", 30, 2);   // 3

  const idsProv = await serviceManager.getServicesByCreator(provider.address);
  expect(idsProv.map(x => x.toString())).to.deep.equal(["1", "2"]);

  const idsOther = await serviceManager.getServicesByCreator(other.address);
  expect(idsOther.map(x => x.toString())).to.deep.equal(["3"]);
});

it("indexing remains stable after removal", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // 1
  await serviceManager.connect(provider).registerService("B", "D", "cat", "type", 20, 1); // 2
  await serviceManager.connect(provider).registerService("C", "D", "cat", "type", 30, 2); // 3

  await serviceManager.connect(provider).removeService(2);

  // getters still use one based indices and point to the same slots
  const m1 = await serviceManager.getServiceMeta(1);
  expect(m1.sid).to.equal(1);
  expect(m1.active).to.equal(true);

  const m2 = await serviceManager.getServiceMeta(2);
  expect(m2.sid).to.equal(2);
  expect(m2.active).to.equal(false); // removed

  const m3 = await serviceManager.getServiceMeta(3);
  expect(m3.sid).to.equal(3);
  expect(m3.active).to.equal(true);

  // count stays equal to array length
  const count = await serviceManager.getServiceCount();
  expect(count).to.equal(3);

  // all services keep their positions in the returned array
  const all = await serviceManager.getAllServices();
  expect(all[0].id).to.equal(1);
  expect(all[1].id).to.equal(2);
  expect(all[2].id).to.equal(3);
});

it("reactivation keeps the same id and index", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // 1
  await serviceManager.connect(provider).removeService(1);

  const before = await serviceManager.getService(1);
  expect(before.id).to.equal(1);
  expect(before.active).to.equal(false);

  await serviceManager.connect(provider).activateService(1);

  const after = await serviceManager.getService(1);
  expect(after.id).to.equal(1);
  expect(after.active).to.equal(true);
});

it("busy flag read via getServiceMeta for a given index", async function () {
  await serviceManager.connect(provider).registerService("A", "D", "cat", "type", 10, 0); // 1

  let meta = await serviceManager.getServiceMeta(1);
  expect(meta.busy).to.equal(false);

  await serviceManager.connect(provider).setBusy(1, true);
  meta = await serviceManager.getServiceMeta(1);
  expect(meta.busy).to.equal(true);

  await mockOrg.callSetBusy(await serviceManager.getAddress(), 1, false);
  meta = await serviceManager.getServiceMeta(1);
  expect(meta.busy).to.equal(false);
});

});