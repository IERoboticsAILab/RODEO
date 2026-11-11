// Header control: connect MetaMask, show address and IEC balance, switch network,
// and (local chain only) get test funds.
import { useState } from "react";
import { shortAddress, useWallet } from "../lib/wallet";

export default function WalletButton() {
  const w = useWallet();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  if (!w.config) return null;
  if (!w.connected) {
    return (
      <div className="flex items-center gap-2">
        {w.error ? <span className="text-xs text-red-600 max-w-[16rem] truncate" title={w.error}>{w.error}</span> : null}
        <button className="btn btn-default focus-ring" onClick={w.connect} disabled={w.connecting}>
          {w.connecting ? "Connecting..." : "Connect wallet"}
        </button>
      </div>
    );
  }
  if (!w.onRightChain) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono">{shortAddress(w.address)}</span>
        <button className="btn btn-default focus-ring" onClick={w.switchNetwork}>
          Switch to {w.config.chainName}
        </button>
      </div>
    );
  }

  const lowFunds = w.iec !== undefined && (w.iec < 1 || (w.eth ?? 0) < 0.01);
  async function faucet() {
    setBusy(true);
    setNote("");
    try { await w.requestFaucet(); setNote("funded"); }
    catch (e: any) { setNote(e?.message || String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex items-center gap-2">
      {note ? <span className="text-xs opacity-70 max-w-[14rem] truncate" title={note}>{note}</span> : null}
      {w.config.faucet && lowFunds ? (
        <button className="btn focus-ring" onClick={faucet} disabled={busy}
                title={`Local chain only: ${w.config.faucetIec} ${w.config.tokenSymbol} and ${w.config.faucetEth} ETH for gas`}>
          {busy ? "Funding..." : "Get test funds"}
        </button>
      ) : null}
      <span className="text-sm whitespace-nowrap" title={w.address}>
        <span className="font-mono text-xs">{shortAddress(w.address)}</span>
        {" · "}{w.iec !== undefined ? `${Math.round(w.iec * 100) / 100} ${w.config.tokenSymbol}` : "..."}
      </span>
      <button className="btn btn-ghost focus-ring" onClick={w.disconnect} aria-label="Disconnect wallet">Disconnect</button>
    </div>
  );
}
