// Wallet support (MetaMask) for the console, with MetaMask Connect EVM
// (@metamask/connect-evm, the successor of the deprecated @metamask/sdk).
//
// Posting a task from the connected wallet: the backend checks it and returns
// the description (/tasks/prepare); the wallet then approves the TaskManager for
// the reward and calls TaskManager.registerTask, so the connected address is the
// task's creator and payer (and receives the refund if the task is rejected).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { BrowserProvider, Contract, formatUnits } from "ethers";
import { API_BASE } from "./api";

export type WalletConfig = {
  chainId: number;
  chainName: string;
  rpcUrl: string;
  currencySymbol: string;
  taskManager: string;
  iecoin: string;
  organization: string;
  tokenSymbol: string;
  faucet: boolean;
  faucetEth: number;
  faucetIec: number;
};

export type PreparedTask = {
  description: string;
  category: string;
  taskType: string;
  rewardWei: string;
  taskManager: string;
};

const IECOIN_ABI = [
  "function balanceOf(address owner) view returns (uint256)",
  "function allowance(address owner, address spender) view returns (uint256)",
  "function approve(address spender, uint256 amount) returns (bool)",
];
const TASK_MANAGER_ABI = [
  "function registerTask(string description, string category, string taskType, uint256 reward) returns (uint256)",
  "function removeTask(uint256 taskId)",
  "function activateTask(uint256 taskId)",
];

const hexChain = (id: number) => `0x${id.toString(16)}` as `0x${string}`;

type WalletState = {
  config?: WalletConfig;
  address?: string;
  chainId?: number;
  iec?: number;
  eth?: number;
  connecting: boolean;
  error?: string;
};

type WalletApi = WalletState & {
  connected: boolean;          // an account is connected
  onRightChain: boolean;       // ... and MetaMask is on the console's chain
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  switchNetwork: () => Promise<void>;
  refresh: () => Promise<void>;
  postTask: (p: PreparedTask) => Promise<string>;
  // creator-only actions on a task this wallet posted
  removeTask: (taskId: number) => Promise<string>;
  activateTask: (taskId: number, rewardWei: string) => Promise<string>;
  requestFaucet: () => Promise<string>;
};

const Ctx = createContext<WalletApi | null>(null);

// one MetaMask Connect client per page (the library keeps a singleton)
let clientPromise: Promise<any> | null = null;
const listeners = {
  accounts: (_a: string[]) => {},
  chain: (_c: string) => {},
  disconnect: () => {},
};

function getClient(cfg: WalletConfig): Promise<any> {
  if (!clientPromise) {
    clientPromise = import("@metamask/connect-evm").then(m =>
      m.createEVMClient({
        dapp: { name: "RODEO Organization Console", url: window.location.origin },
        api: { supportedNetworks: { [hexChain(cfg.chainId)]: cfg.rpcUrl } },
        eventHandlers: {
          accountsChanged: (a: string[]) => listeners.accounts(a),
          chainChanged: (c: string) => listeners.chain(c),
          disconnect: () => listeners.disconnect(),
        },
      }));
  }
  return clientPromise;
}

async function readJson<T>(r: Response): Promise<T> {
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((body as any)?.detail || `HTTP ${r.status}`);
  return body as T;
}

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [s, setS] = useState<WalletState>({ connecting: false });
  const stateRef = useRef(s);
  stateRef.current = s;

  // the console's chain and contracts
  useEffect(() => {
    fetch(`${API_BASE}/wallet/config`).then(r => readJson<WalletConfig>(r))
      .then(config => setS(p => ({ ...p, config })))
      .catch(e => setS(p => ({ ...p, error: `wallet config: ${e.message}` })));
  }, []);

  const provider = useCallback(async () => {
    const cfg = stateRef.current.config;
    if (!cfg) throw new Error("wallet configuration not loaded");
    const client = await getClient(cfg);
    return new BrowserProvider(client.getProvider());
  }, []);

  const refresh = useCallback(async () => {
    const { config, address, chainId } = stateRef.current;
    if (!config || !address || chainId !== config.chainId) return;
    try {
      const p = await provider();
      const iec = new Contract(config.iecoin, IECOIN_ABI, p);
      const [tok, wei] = await Promise.all([iec.balanceOf(address), p.getBalance(address)]);
      setS(prev => ({ ...prev, iec: Number(formatUnits(tok, 18)), eth: Number(formatUnits(wei, 18)) }));
    } catch (e: any) {
      setS(prev => ({ ...prev, error: `balance: ${e?.shortMessage || e?.message || e}` }));
    }
  }, [provider]);

  // wallet events from MetaMask
  useEffect(() => {
    listeners.accounts = (a: string[]) =>
      setS(p => ({ ...p, address: a[0], iec: undefined, eth: undefined }));
    listeners.chain = (c: string) => setS(p => ({ ...p, chainId: parseInt(c, 16), iec: undefined }));
    listeners.disconnect = () => setS(p => ({ ...p, address: undefined, chainId: undefined, iec: undefined, eth: undefined }));
  }, []);

  useEffect(() => { refresh(); }, [s.address, s.chainId, refresh]);
  useEffect(() => {
    const t = setInterval(() => refresh(), 10000);
    return () => clearInterval(t);
  }, [refresh]);

  const connect = useCallback(async () => {
    const cfg = stateRef.current.config;
    if (!cfg) return;
    setS(p => ({ ...p, connecting: true, error: undefined }));
    try {
      const client = await getClient(cfg);
      const { accounts, chainId } = await client.connect({ chainIds: [hexChain(cfg.chainId)] });
      setS(p => ({ ...p, address: accounts[0], chainId: parseInt(chainId, 16), connecting: false }));
    } catch (e: any) {
      setS(p => ({ ...p, connecting: false, error: e?.message || String(e) }));
    }
  }, []);

  const disconnect = useCallback(async () => {
    const cfg = stateRef.current.config;
    if (cfg) {
      try { await (await getClient(cfg)).disconnect(); } catch { /* already disconnected */ }
    }
    setS(p => ({ ...p, address: undefined, chainId: undefined, iec: undefined, eth: undefined }));
  }, []);

  const switchNetwork = useCallback(async () => {
    const cfg = stateRef.current.config;
    if (!cfg) return;
    try {
      const client = await getClient(cfg);
      await client.switchChain({
        chainId: hexChain(cfg.chainId),
        chainConfiguration: {
          chainName: cfg.chainName,
          nativeCurrency: { name: cfg.currencySymbol, symbol: cfg.currencySymbol, decimals: 18 },
          rpcUrls: [cfg.rpcUrl],
        },
      });
      setS(p => ({ ...p, chainId: cfg.chainId, error: undefined }));
    } catch (e: any) {
      setS(p => ({ ...p, error: e?.message || String(e) }));
    }
  }, []);

  const postTask = useCallback(async (prep: PreparedTask) => {
    const { config, address, chainId } = stateRef.current;
    if (!config || !address) throw new Error("connect a wallet first");
    if (chainId !== config.chainId) throw new Error(`switch MetaMask to ${config.chainName} first`);
    const signer = await (await provider()).getSigner(address);
    const reward = BigInt(prep.rewardWei);
    const iec = new Contract(config.iecoin, IECOIN_ABI, signer);
    const balance: bigint = await iec.balanceOf(address);
    if (balance < reward) {
      throw new Error(`your wallet holds ${formatUnits(balance, 18)} ${config.tokenSymbol}, ` +
                      `less than the ${formatUnits(reward, 18)} reward`);
    }
    // 1. let the TaskManager take the reward into escrow (MetaMask asks to confirm)
    const allowance: bigint = await iec.allowance(address, prep.taskManager);
    if (allowance < reward) {
      await (await iec.approve(prep.taskManager, reward)).wait();
    }
    // 2. post the task (MetaMask asks to confirm); this wallet is the creator and payer
    const tm = new Contract(prep.taskManager, TASK_MANAGER_ABI, signer);
    const tx = await tm.registerTask(prep.description, prep.category, prep.taskType, reward);
    await tx.wait();
    await refresh();
    return tx.hash as string;
  }, [provider, refresh]);

  const signerFor = useCallback(async () => {
    const { config, address, chainId } = stateRef.current;
    if (!config || !address) throw new Error("connect a wallet first");
    if (chainId !== config.chainId) throw new Error(`switch MetaMask to ${config.chainName} first`);
    return { config, address, signer: await (await provider()).getSigner(address) };
  }, [provider]);

  const removeTask = useCallback(async (taskId: number) => {
    const { config, signer } = await signerFor();
    const tm = new Contract(config.taskManager, TASK_MANAGER_ABI, signer);
    const tx = await tm.removeTask(taskId);
    await tx.wait();
    return tx.hash as string;
  }, [signerFor]);

  const activateTask = useCallback(async (taskId: number, rewardWei: string) => {
    // the contract takes the reward into escrow again, so approve it first
    const { config, address, signer } = await signerFor();
    const reward = BigInt(rewardWei);
    const iec = new Contract(config.iecoin, IECOIN_ABI, signer);
    const balance: bigint = await iec.balanceOf(address);
    if (balance < reward) {
      throw new Error(`reactivating takes the ${formatUnits(reward, 18)} ${config.tokenSymbol} reward again ` +
                      `(removing did not refund it); your wallet holds ${formatUnits(balance, 18)}`);
    }
    if ((await iec.allowance(address, config.taskManager)) < reward) {
      await (await iec.approve(config.taskManager, reward)).wait();
    }
    const tm = new Contract(config.taskManager, TASK_MANAGER_ABI, signer);
    const tx = await tm.activateTask(taskId);
    await tx.wait();
    await refresh();
    return tx.hash as string;
  }, [signerFor, refresh]);

  const requestFaucet = useCallback(async () => {
    const { address } = stateRef.current;
    if (!address) throw new Error("connect a wallet first");
    const r = await readJson<{ ethTx: string; iecTx: string }>(await fetch(`${API_BASE}/faucet`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address }) }));
    await refresh();
    return r.iecTx;
  }, [refresh]);

  const api = useMemo<WalletApi>(() => ({
    ...s,
    connected: !!s.address,
    onRightChain: !!s.address && !!s.config && s.chainId === s.config.chainId,
    connect, disconnect, switchNetwork, refresh, postTask, removeTask, activateTask, requestFaucet,
  }), [s, connect, disconnect, switchNetwork, refresh, postTask, removeTask, activateTask, requestFaucet]);

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useWallet(): WalletApi {
  const w = useContext(Ctx);
  if (!w) throw new Error("useWallet outside WalletProvider");
  return w;
}

export function shortAddress(a?: string): string {
  return a && a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a || "";
}
