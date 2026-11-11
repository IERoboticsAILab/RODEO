// Admin mode: unlocks the controls that make the console sign with the
// organization's wallet (posting for the organization, deposits, the
// organization's services). Without it, people post with their own wallets.
// The backend enforces this (ORG_ADMIN_PIN); the page only hides what would be refused.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { checkAdminPin, fetchAdminStatus, getAdminPin, setAdminPin } from "./api";

type AdminApi = {
  enabled: boolean;          // the console has an admin PIN at all
  unlocked: boolean;         // ... and it was entered in this tab
  unlock: (pin: string) => Promise<void>;
  lock: () => void;
};

const Ctx = createContext<AdminApi | null>(null);

export function AdminProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(false);
  const [unlocked, setUnlocked] = useState(false);

  useEffect(() => {
    fetchAdminStatus().then(async st => {
      setEnabled(st.enabled);
      const pin = getAdminPin();
      if (st.enabled && pin) {
        try { await checkAdminPin(pin); setUnlocked(true); } catch { setAdminPin(""); }
      }
    }).catch(() => setEnabled(false));
  }, []);

  const unlock = useCallback(async (pin: string) => {
    await checkAdminPin(pin);        // throws "admin PIN required..." when wrong
    setAdminPin(pin);
    setUnlocked(true);
  }, []);

  const lock = useCallback(() => { setAdminPin(""); setUnlocked(false); }, []);

  const api = useMemo(() => ({ enabled, unlocked, unlock, lock }), [enabled, unlocked, unlock, lock]);
  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useAdmin(): AdminApi {
  const a = useContext(Ctx);
  if (!a) throw new Error("useAdmin outside AdminProvider");
  return a;
}
