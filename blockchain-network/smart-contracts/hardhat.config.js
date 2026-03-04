import "@nomicfoundation/hardhat-toolbox";
import "dotenv/config";

const GANACHE_URL = process.env.GANACHE_URL || "http://127.0.0.1:8545";

const accounts = [
  process.env.PRIVATE_KEY_DEPLOYER,
  process.env.PRIVATE_KEY_ORGANIZATION,
  process.env.PRIVATE_KEY_ORACLE,
  process.env.PRIVATE_KEY_HUMAN,
  process.env.PRIVATE_KEY_ROBOT,
].filter(Boolean);
/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.28",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      },
      viaIR: true
    }
    },
  networks: {
    ganache: {
      url: GANACHE_URL,
      chainId: 1337,
      accounts,
    },
  },
};
