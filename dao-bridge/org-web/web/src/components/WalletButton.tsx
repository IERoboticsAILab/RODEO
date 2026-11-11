// Header control: connect MetaMask, show address and IEC balance, switch network,
// and (local chain only) get test funds.
import { useState } from "react";
import { shortAddress, useWallet } from "../lib/wallet";

// MetaMask's orange, so the control is recognisably MetaMask
const MM_ORANGE = "#F6851B";
const mmButton: React.CSSProperties = { background: MM_ORANGE, borderColor: MM_ORANGE, color: "white" };
const mmChip: React.CSSProperties = { borderColor: MM_ORANGE };

// MetaMask's official icon, if web/public/metamask.svg has been added (from
// MetaMask's brand resources); otherwise nothing is drawn.
function MetaMaskIcon() {
  const [ok, setOk] = useState(true);
  if (!ok) return null;
  return <img src="/metamask.svg" alt="" className="size-5" onError={() => setOk(false)} />;
}

export default function WalletButton() {
  const w = useWallet();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  if (!w.config) return null;
  if (!w.connected) {
    return (
      <div className="flex items-center gap-2">
        {w.error ? <span className="text-xs text-red-600 max-w-[16rem] truncate" title={w.error}>{w.error}</span> : null}
        <button className="btn focus-ring flex items-center gap-2 font-semibold" style={mmButton}
                onClick={w.connect} disabled={w.connecting}>
          <MetaMaskIcon />
          {w.connecting ? "Connecting to MetaMask..." : "Connect MetaMask"}
        </button>
      </div>
    );
  }
  if (!w.onRightChain) {
    return (
      <div className="flex items-center gap-2 rounded-lg border px-2 py-1" style={mmChip}>
        <MetaMaskIcon />
        <span className="text-xs font-mono">{shortAddress(w.address)}</span>
        <button className="btn focus-ring font-semibold" style={mmButton} onClick={w.switchNetwork}>
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
      <span className="flex items-center gap-2 rounded-lg border px-2 py-1 text-sm whitespace-nowrap"
            style={mmChip} title={`MetaMask: ${w.address}`}>
        <MetaMaskIcon />
        <span className="text-xs font-semibold" style={{ color: MM_ORANGE }}>MetaMask</span>
        <span className="font-mono text-xs">{shortAddress(w.address)}</span>
        <span>{w.iec !== undefined ? `${Math.round(w.iec * 100) / 100} ${w.config.tokenSymbol}` : "..."}</span>
      </span>
      <button className="btn btn-ghost focus-ring" onClick={w.disconnect} aria-label="Disconnect MetaMask">Disconnect</button>
    </div>
  );
}
