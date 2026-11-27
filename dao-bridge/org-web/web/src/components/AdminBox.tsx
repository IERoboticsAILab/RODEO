// Home page: the organization's admin area. Locked, it asks for the admin PIN;
// unlocked, it shows the organization's task funds and the deposit box.
import { useState } from "react";
import { useAdmin } from "../lib/admin";

export default function AdminBox({ children }: { children: React.ReactNode }) {
  const admin = useAdmin();
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const unlock = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await admin.unlock(pin); setPin(""); }
    catch (err: any) { setError(err?.message || String(err)); }
    finally { setBusy(false); }
  };

  if (!admin.enabled) {
    return (
      <p className="text-sm opacity-70">
        The organization's wallet is not available on this console (no admin PIN is set):
        tasks are posted and paid with people's own wallets.
      </p>
    );
  }
  if (!admin.unlocked) {
    return (
      <form onSubmit={unlock} className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="label">Admin PIN</label>
          <input type="password" className="input focus-ring w-40" value={pin} autoComplete="off"
                 onChange={e => setPin(e.target.value)} required />
        </div>
        <button className="btn focus-ring" type="submit" disabled={busy}>{busy ? "Checking..." : "Unlock"}</button>
        <span className="text-xs opacity-70 basis-full">
          Unlocks posting and paying from the organization's wallet, its deposit, and its services, in this browser tab.
        </span>
        {error ? <p className="text-sm text-red-600 basis-full">{error}</p> : null}
      </form>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold">Admin unlocked</span>
        <button className="btn btn-ghost focus-ring" onClick={admin.lock}>Lock</button>
      </div>
      {children}
    </div>
  );
}
