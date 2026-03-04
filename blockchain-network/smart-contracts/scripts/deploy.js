import hardhat from "hardhat";
const { ethers, network } = hardhat;
import fs from "node:fs";
import path from "node:path";

// ✅ ADD THIS HELPER (near top, under requires)
function saveDeployment(chainId, payload) {
  const dir = path.join(process.cwd(), "deployments");
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const file = path.join(dir, `${chainId}.json`);
  fs.writeFileSync(file, JSON.stringify(payload, null, 2));
  console.log(`📝 Saved deployment to ${file}`);
}

async function main() {
  // Get deployer and organization signer accounts
  const [deployer, organizationOwner, oracleSigner, humanWallet, robotWallet] = await ethers.getSigners();

  // === Deploy IECoin ===
  const initialSupply = ethers.parseEther("1000000"); // 1,000,000 IEC
  const IECoin = await ethers.getContractFactory("contracts/IECoin.sol:IECoin");
  const iecoin = await IECoin.connect(deployer).deploy(initialSupply, deployer.address);
  await iecoin.waitForDeployment();

    // === Deploy Organization with dummy taskManager address ===
  const Organization = await ethers.getContractFactory("contracts/Organization.sol:Organization");
  const dummyAddress = ethers.ZeroAddress;
  const organization = await Organization.connect(organizationOwner).deploy(iecoin.target);
  await organization.waitForDeployment();


    // === Deploy ServiceManager ===
  const ServiceManager = await ethers.getContractFactory("contracts/ServiceManager.sol:ServiceManager");
  const serviceManager = await ServiceManager.connect(organizationOwner).deploy(organization.target);
  await serviceManager.waitForDeployment();

    // === Tell Organization about its ServiceManager ===
  const setSvcTx = await organization
    .connect(organizationOwner)
    .setServiceManager(serviceManager.target)
  await setSvcTx.wait()


  // === Deploy TaskManager with actual organization address ===
  const TaskManager = await ethers.getContractFactory("contracts/TaskManager.sol:TaskManager");
  const taskManager = await TaskManager.connect(organizationOwner).deploy(
    iecoin.target,
    organization.target
  );
  await taskManager.waitForDeployment();

  // === Set actual taskManager address in Organization and set the Oracle address in task Manager===
  const setTx = await organization.connect(organizationOwner).setTaskManager(taskManager.target);
  await setTx.wait();

    // Set the oracle through Organization so TaskManager stores it
  const oracleAddress = oracleSigner.address; // replace if you have a specific oracle address
  await (await organization.connect(organizationOwner).setOracle(oracleAddress)).wait();

  // === Log deployed addresses ===
  console.log("✅ Contracts deployed successfully:\n");
  console.log(`IECoin:          ${iecoin.target}`);
  console.log(`Organization:    ${organization.target}`);
  console.log(`ServiceManager:  ${serviceManager.target}`);
  console.log(`TaskManager:     ${taskManager.target}`);

  const net = await ethers.provider.getNetwork();
  const chainId = Number(net.chainId);

  saveDeployment(chainId, {
    chainId,
    network: network.name,
    timestamp: new Date().toISOString(),
    contracts: {
      IECoin: { address: iecoin.target },
      Organization: { address: organization.target },
      ServiceManager: { address: serviceManager.target },
      TaskManager: { address: taskManager.target },
    },
  });

  // === Transfer 2000 IEC to human, organization, and robot wallets ===
  console.log("\n💰 Distributing IEC tokens...\n");
  
  const transferAmount = ethers.parseEther("2000"); // 2000 IEC
  
  const transfers = [
    { name: "Human", wallet: humanWallet, address: humanWallet.address },
    { name: "Organization", wallet: organizationOwner, address: organizationOwner.address },
    { name: "Robot", wallet: robotWallet, address: robotWallet.address }
  ];

  for (const transfer of transfers) {
    const tx = await iecoin.connect(deployer).transfer(transfer.address, transferAmount);
    await tx.wait();
    const balance = await iecoin.balanceOf(transfer.address);
    console.log(`✅ Transferred 2000 IEC to ${transfer.name} (${transfer.address})`);
    console.log(`   Balance: ${ethers.formatEther(balance)} IEC`);
  }

  console.log("\n✅ Token distribution complete!");

  // === Fund Organization Contract ===
  console.log("\n💼 Funding Organization contract for task rewards...\n");
  
  const fundingAmount = ethers.parseEther("1000"); // Fund with 1000 IEC
  
  // First approve Organization contract to spend tokens
  const approveTx = await iecoin.connect(organizationOwner).approve(organization.target, fundingAmount);
  await approveTx.wait();
  console.log(`✅ Approved Organization contract to spend ${ethers.formatEther(fundingAmount)} IEC`);
  
  // Deposit tokens into Organization contract (this also approves TaskManager)
  const depositTx = await organization.connect(organizationOwner).deposit(fundingAmount);
  await depositTx.wait();
  
  const orgBalance = await iecoin.balanceOf(organization.target);
  console.log(`✅ Deposited ${ethers.formatEther(fundingAmount)} IEC into Organization contract`);
  console.log(`   Organization contract balance: ${ethers.formatEther(orgBalance)} IEC`);
  console.log(`   ℹ️  This allows creating tasks with up to ${ethers.formatEther(orgBalance)} total rewards`);
  
  console.log("\n🎉 Deployment complete! Organization is ready to create tasks.");

}

main().catch((error) => {
  console.error("❌ Deployment failed:", error);
  process.exitCode = 1;
});
