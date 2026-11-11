// src/components/Forms.tsx

import { useEffect, useMemo, useState } from "react";
import type { CatalogEntry, ParamSpec } from "../lib/types";

export type TaskRequest = {
  title: string;                                // the task's name
  category: string;
  taskType: string;
  rewardIec: number;
  description: string;                          // free-text note
  params: Record<string, string | number>;      // service details ({} if the service has none)
};

type TaskFormProps = {
  catalog: CatalogEntry[] | undefined;
  onCreate: (req: TaskRequest) => Promise<void>;
};

function availability(e: CatalogEntry): string {
  const who = e.robot ? ` · offered by ${e.robot}` : "";
  if (e.free > 0) return `${e.free} of ${e.providers} free · from ${e.minPriceIec} IEC${who}`;
  return `all ${e.providers} busy, the task will queue · from ${e.minPriceIec} IEC${who}`;
}

function defaultsFor(e: CatalogEntry | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!e) return out;
  for (const [name, spec] of Object.entries(e.params)) {
    out[name] = spec.default !== undefined ? String(spec.default) : "";
  }
  return out;
}

function ParamField({ name, spec, entry, value, onChange }: {
  name: string; spec: ParamSpec; entry: CatalogEntry; value: string; onChange: (v: string) => void;
}) {
  const label = `${spec.label || name}${spec.optional ? " (optional)" : ""}`;
  if (spec.type === "place") {
    return (
      <div className="space-y-1">
        <label className="label">{label}</label>
        <select className="input focus-ring" value={value} onChange={e => onChange(e.target.value)}
                required={!spec.optional}>
          {spec.optional || !value ? <option value="">-</option> : null}
          {Object.entries(entry.places).map(([id, p]) => (
            <option key={id} value={id}>{p.label}</option>
          ))}
        </select>
      </div>
    );
  }
  return (
    <div className="space-y-1">
      <label className="label">{label}</label>
      <input className="input focus-ring" type={spec.type === "number" ? "number" : "text"}
             step={spec.type === "number" ? "any" : undefined}
             value={value} onChange={e => onChange(e.target.value)} required={!spec.optional} />
    </div>
  );
}

/**
 * Task form, the same for every service:
 *   Name | Description | Category | Type | Price
 * Category and Type are dropdowns of what the services online offer, empty at
 * first. Choosing a type sets the price and opens a "<service> details"
 * section with only the fields that service declares (e.g. a delivery's
 * places); fixed services have none. Offline services do not appear; busy ones
 * are marked as queueing.
 */
export function CreateTaskForm({ catalog, onCreate }: TaskFormProps) {
  const [category, setCategory] = useState("");
  const [taskType, setTaskType] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [reward, setReward] = useState<number | "">("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const categories = useMemo(
    () => Array.from(new Set((catalog ?? []).map(e => e.category))).sort(), [catalog]);
  const types = useMemo(
    () => (catalog ?? []).filter(e => e.category === category), [catalog, category]);
  const entry = useMemo(
    () => types.find(e => e.taskType === taskType), [types, taskType]);

  // services come and go: drop a selection that is no longer offered
  useEffect(() => {
    if (category && !categories.includes(category)) { setCategory(""); setTaskType(""); }
    else if (taskType && !types.some(e => e.taskType === taskType)) setTaskType("");
  }, [categories, types, category, taskType]);

  // a newly chosen service: its defaults, and the price that gets the task picked up now
  useEffect(() => {
    setValues(defaultsFor(entry));
    setReward(entry ? (entry.free > 0 ? entry.pickPriceIec : entry.minPriceIec) : "");
    setError("");
  }, [entry?.key]);  // eslint-disable-line react-hooks/exhaustive-deps

  function chooseCategory(c: string) {
    setCategory(c);
    const offered = (catalog ?? []).filter(e => e.category === c);
    setTaskType(offered.length === 1 ? offered[0].taskType : "");    // one type: pick it
  }

  if (!catalog) return <p className="text-sm opacity-70">Loading services...</p>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!entry || reward === "") return;
    const params: Record<string, string | number> = {};
    for (const [name, spec] of Object.entries(entry.params)) {
      const v = values[name] ?? "";
      if (v === "") continue;                         // optional, left empty
      params[name] = spec.type === "number" ? Number(v) : v;
    }
    setBusy(true);
    setError("");
    try {
      await onCreate({ title: title.trim(), category: entry.category, taskType: entry.taskType,
                       rewardIec: Number(reward), description: note, params });
      setTitle("");
      setNote("");
      setValues(defaultsFor(entry));
    } catch (err: any) {
      setError(err?.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  const paramNames = entry ? Object.keys(entry.params) : [];
  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <div className="space-y-1 md:col-span-2">
          <label className="label">Name</label>
          <input className="input focus-ring" value={title} onChange={e => setTitle(e.target.value)} required />
        </div>
        <div className="space-y-1 md:col-span-4">
          <label className="label">Description</label>
          <input className="input focus-ring" value={note} onChange={e => setNote(e.target.value)} />
        </div>
        <div className="space-y-1 md:col-span-2">
          <label className="label">Category</label>
          <select className="input focus-ring" value={category} onChange={e => chooseCategory(e.target.value)} required>
            <option value="" disabled>{categories.length ? "Select..." : "No service online"}</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="space-y-1 md:col-span-2">
          <label className="label">Type</label>
          <select className="input focus-ring" value={taskType} onChange={e => setTaskType(e.target.value)}
                  required disabled={!category}>
            <option value="" disabled>{category ? "Select..." : "-"}</option>
            {types.map(e => <option key={e.key} value={e.taskType}>{e.taskType} ({e.name})</option>)}
          </select>
        </div>
        <div className="space-y-1 md:col-span-2">
          <label className="label">Price (IEC)</label>
          <input type="number" className="input focus-ring" value={reward} min={entry?.minPriceIec ?? 0}
                 step="any" onChange={e => setReward(e.target.value === "" ? "" : Number(e.target.value))}
                 required disabled={!entry} />
        </div>
      </div>

      {entry ? (
        <>
          <p className="text-xs opacity-70 -mt-2">
            {entry.name}{entry.summary ? `: ${entry.summary}` : ""} · {availability(entry)}
          </p>

          {paramNames.length > 0 ? (
            <fieldset className="border rounded-md p-3 space-y-2">
              <legend className="px-1 text-sm font-semibold">{entry.name} details</legend>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {paramNames.map(name => (
                  <ParamField key={name} name={name} spec={entry.params[name]} entry={entry}
                              value={values[name] ?? ""} onChange={v => setValues({ ...values, [name]: v })} />
                ))}
              </div>
            </fieldset>
          ) : null}

          <div className="flex items-center gap-3">
            <button className="btn btn-default focus-ring" type="submit" disabled={busy}>
              {busy ? "Posting..." : "Create task"}
            </button>
            <span className="text-xs opacity-70">
              The robot is paid its service price; a price above it stays in the contract.
            </span>
          </div>
        </>
      ) : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </form>
  );
}

/** Funds the organization can still put into tasks, and a deposit box. */
export function TaskFunds({ funds, onDeposit }: {
  funds: { taskFundsIec: number; walletIec: number } | undefined;
  onDeposit: (amountIec: number) => Promise<void>;
}) {
  const [amount, setAmount] = useState(1000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!funds) return null;
  async function deposit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await onDeposit(amount); } catch (err: any) { setError(err?.message || String(err)); }
    finally { setBusy(false); }
  }
  return (
    <form onSubmit={deposit} className="flex flex-wrap items-end gap-3">
      <div className="text-sm">
        <div><span className="font-semibold">Task funds:</span> {funds.taskFundsIec} IEC available</div>
        <div className="text-xs opacity-70">organization wallet: {funds.walletIec} IEC</div>
      </div>
      <div className="space-y-1">
        <label className="label">Deposit (IEC)</label>
        <input type="number" className="input focus-ring w-32" value={amount} min={1}
               onChange={e => setAmount(Number(e.target.value))} />
      </div>
      <button className="btn focus-ring" type="submit" disabled={busy}>{busy ? "Depositing..." : "Deposit"}</button>
      <span className="text-xs opacity-70 basis-full">
        A deposit sets the available funds to the amount deposited (contract behaviour): deposit when they run low.
      </span>
      {error ? <p className="text-sm text-red-600 basis-full">{error}</p> : null}
    </form>
  );
}

type ServiceFormProps = {
  onCreate: (args: { name: string; price: number; category: string; serviceType: string }) => Promise<void> | void;
  setName: (v: string) => void;
  setDescription: (v: string) => void;
  setCategory: (v: string) => void;
  setServiceType: (v: string) => void;
  setPrice: (v: number) => void;
  name: string;
  description: string;
  category: string;
  serviceType: string;
  price: number;
};

export function CreateServiceForm({
  onCreate,
  setName,
  setDescription,
  setCategory,
  setServiceType,
  setPrice,
  name,
  description,
  category,
  serviceType,
  price,
}: ServiceFormProps) {
  return (
    <form
      onSubmit={async e => {
        e.preventDefault();
        await onCreate({ name, price, category, serviceType });
        setName("");
        setDescription("");
        setCategory("");
        setServiceType("");
        setPrice(0);
      }}
      className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
    >
      <div className="space-y-1 md:col-span-2">
        <label className="label">Name</label>
        <input className="input focus-ring" value={name} onChange={e => setName(e.target.value)} required />
      </div>

      {/* Use input to keep a single row, like tasks */}
      <div className="space-y-1 md:col-span-4">
        <label className="label">Description</label>
        <input className="input focus-ring" value={description} onChange={e => setDescription(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Category</label>
        <input className="input focus-ring" value={category} onChange={e => setCategory(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Type</label>
        <input className="input focus-ring" value={serviceType} onChange={e => setServiceType(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-1">
        <label className="label">Price</label>
        <input type="number" className="input focus-ring" value={price} onChange={e => setPrice(Number(e.target.value))} min={0} />
      </div>

      <div className="md:col-span-1 flex md:block">
        <button className="btn btn-default focus-ring w-full md:w-auto" type="submit">
          Create service
        </button>
      </div>
    </form>
  );
}
