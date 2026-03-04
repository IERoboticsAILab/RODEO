import { formatUnitsString  } from "./units";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://10.205.10.9:8080"


async function j<T>(resOrPromise: Response | Promise<Response>): Promise<T> {
  const res = await resOrPromise; // accept Promise<Response> and await it
  if (!res.ok) {
    // try to parse JSON error, fall back to status text
    const contentType = res.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    const err = isJson ? await res.json().catch(() => ({})) : await res.text().catch(() => "");
    const detail = typeof err === "object" && err && "detail" in err ? (err as any).detail : undefined;
    throw new Error(detail || (typeof err === "string" && err) || res.statusText);
  }
  return res.json();
}

export const api = {
  contracts: () => j<import("./types").Contracts>(fetch(`${API_BASE}/contracts`)),

  tasks: {
    all: () => j<import("./types").Task[]>(fetch(`${API_BASE}/tasks`)),
    assigned: () => j<import("./types").Task[]>(fetch(`${API_BASE}/tasks/assigned-to-org`)),
    byCreator: (addr?: string) =>
      j<import("./types").Task[]>(
        fetch(`${API_BASE}/tasks/by-creator${addr ? `?creator=${addr}` : ""}`)
      ),
    register: (body: { description: string; category: string; taskType: string; rewardIec: number }) =>
      j<{ txHash: string }>(
        fetch(`${API_BASE}/tasks/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      ),
    activate: (taskId: number) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/tasks/activate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskId }) })),
    remove: (taskId: number) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/tasks/remove`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskId }) })),
    unassign: (taskId: number) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/tasks/unassign`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskId }) })),
    submitProof: (taskId: number, proofURI: string) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/tasks/submit-proof`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskId, proofURI }) })),
  },

  services: {
    all: () => j<import("./types").Service[]>(fetch(`${API_BASE}/services`)),
    byCreator: (addr?: string) =>
      j<import("./types").Service[]>(
        fetch(`${API_BASE}/services/by-creator${addr ? `?creator=${addr}` : ""}`)
      ),
    register: (body: { name: string; description: string; category: string; serviceType: string; priceIec: number }) =>
      j<{ txHash: string }>(
        fetch(`${API_BASE}/services/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      ),
    activate: (serviceId: number) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/services/activate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ serviceId }) })),
    remove: (serviceId: number) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/services/remove`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ serviceId }) })),
    setBusy: (index: number, isBusy: boolean) =>
      j<{ txHash: string }>(fetch(`${API_BASE}/services/set-busy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index, isBusy }) })),
  },
}

// handy wrappers so pages can import named helpers
//export const fetchTasks = async () => {
  //const [mine, all] = await Promise.all([api.tasks.byCreator(), api.tasks.all()]);
  //return { mine, all };
//};
export const fetchTasks = async () => {
  const [mineRaw, allRaw] = await Promise.all([api.tasks.byCreator(), api.tasks.all()]);
  const mapTask = (t: any) => ({
    ...t,
    // always provide a token string
    rewardToken: t.rewardIec != null
      ? String(t.rewardIec)
      : formatUnitsString(t.rewardWei, 18, 4),
  });
  return { mine: mineRaw.map(mapTask), all: allRaw.map(mapTask) };
};

export const createTask = (body: { description: string; category: string; taskType: string; rewardIec: number }) =>
  api.tasks.register(body);
export const deleteTask = (id: number) => api.tasks.remove(id);
export const activateTask = (id: number) => api.tasks.activate(id);

// mirrors for services pages
//export const fetchServices = async () => {
  //const [mine, all] = await Promise.all([api.services.byCreator(), api.services.all()]);
  //return { mine, all };
//};
export const fetchServices = async () => {
  const [mineRaw, allRaw] = await Promise.all([api.services.byCreator(), api.services.all()]);
  const mapService = (s: any) => ({
    ...s,
    // always provide a token string
    priceToken: s.priceIec != null
      ? String(s.priceIec)
      : formatUnitsString(s.priceWei, 18, 4),
  });
  return { mine: mineRaw.map(mapService), all: allRaw.map(mapService) };
};
export const createService = (body: { name: string; description: string; category: string; serviceType: string; priceIec: number }) =>
  api.services.register(body);
export const deleteService = (id: number) => api.services.remove(id);
export const activateService = (id: number) => api.services.activate(id);
export const setServiceBusy = (index: number, isBusy: boolean) => api.services.setBusy(index, isBusy);

// overview helper for Home
export const fetchAll = async () => {
  const [allTasks, allServices] = await Promise.all([
    api.tasks.all(),
    api.services.all(),
  ]);
  return { allTasks, allServices };
};

// lib/api.ts
export const fetchTokenHolders = async () => {
  const res = await j<{
    token: { address: string; symbol: string; decimals: number };
    holders: Array<{ address: string; balanceWei: string; balanceIec?: string }>;
  }>(fetch(`${API_BASE}/token/holders`));

  const holders = res.holders.map(h => ({
    address: h.address,
    // prefer server provided IEC string, else format from wei
    balance: h.balanceIec ?? formatUnitsString(h.balanceWei, res.token.decimals ?? 18, 4),
  }));

  return { token: res.token, holders };
};

