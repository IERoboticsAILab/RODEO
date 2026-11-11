// src/components/Forms.tsx

import { useEffect, useMemo, useState } from "react";
import type { CatalogEntry, ParamSpec } from "../lib/types";

export type TaskRequest = {
  category: string;
  taskType: string;
  rewardIec: number;
  description: string;                          // free-text note
  params?: Record<string, string | number>;     // only for services with a parameter schema
};

type TaskFormProps = {
  catalog: CatalogEntry[] | undefined;
  onCreate: (req: TaskRequest) => Promise<void>;
};

function availability(e: CatalogEntry): string {
  if (e.free > 0) return `${e.free} of ${e.providers} free`;
  return `all ${e.providers} busy - will queue`;
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
 * Task form driven by the services that are online (GET /catalog): pick a
 * service, fill its parameters (places are dropdowns), add a note, and post.
 * Offline services do not appear; busy ones are marked "will queue".
 */
export function CreateTaskForm({ catalog, onCreate }: TaskFormProps) {
  const [key, setKey] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [reward, setReward] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const entry = useMemo(() => catalog?.find(e => e.key === key), [catalog, key]);

  // keep a valid selection as services come and go
  useEffect(() => {
    if (!catalog || catalog.length === 0) { setKey(""); return; }
    if (!catalog.some(e => e.key === key)) setKey(catalog[0].key);
  }, [catalog, key]);

  // new service: its defaults, and the reward that gets the task picked up now
  useEffect(() => {
    setValues(defaultsFor(entry));
    setReward(entry ? (entry.free > 0 ? entry.pickPriceIec : entry.minPriceIec) : 0);
    setError("");
  }, [entry?.key]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!catalog) return <p className="text-sm opacity-70">Loading services...</p>;
  if (catalog.length === 0) {
    return <p className="text-sm opacity-70">No service is online. Tasks can be posted once a robot or station has registered a service.</p>;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!entry) return;
    let params: Record<string, string | number> | undefined;
    if (entry.structured) {
      params = {};
      for (const [name, spec] of Object.entries(entry.params)) {
        const v = values[name] ?? "";
        if (v === "") continue;                       // optional, left empty
        params[name] = spec.type === "number" ? Number(v) : v;
      }
    }
    setBusy(true);
    setError("");
    try {
      await onCreate({ category: entry.category, taskType: entry.taskType, rewardIec: reward,
                       description: note, params });
      setValues(defaultsFor(entry));
      setNote("");
    } catch (err: any) {
      setError(err?.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  const paramNames = entry ? Object.keys(entry.params) : [];
  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <div className="space-y-1 md:col-span-5">
          <label className="label">Service</label>
          <select className="input focus-ring" value={key} onChange={e => setKey(e.target.value)}>
            {catalog.map(e => (
              <option key={e.key} value={e.key}>
                {e.name} ({e.category}/{e.taskType}) - from {e.minPriceIec} IEC, {availability(e)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1 md:col-span-5">
          <label className="label">Note</label>
          <input className="input focus-ring" value={note} onChange={e => setNote(e.target.value)}
                 placeholder="anything the robot or recipient should know" />
        </div>
        <div className="space-y-1 md:col-span-2">
          <label className="label">Reward (IEC)</label>
          <input type="number" className="input focus-ring" value={reward} min={entry?.minPriceIec ?? 0}
                 step="any" onChange={e => setReward(Number(e.target.value))} required />
        </div>
      </div>

      {entry?.summary ? <p className="text-sm opacity-70">{entry.summary}</p> : null}

      {paramNames.length > 0 && entry ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {paramNames.map(name => (
            <ParamField key={name} name={name} spec={entry.params[name]} entry={entry}
                        value={values[name] ?? ""} onChange={v => setValues({ ...values, [name]: v })} />
          ))}
        </div>
      ) : null}

      <div className="flex items-center gap-3">
        <button className="btn btn-default focus-ring" type="submit" disabled={busy || !entry}>
          {busy ? "Posting..." : "Create task"}
        </button>
        <span className="text-xs opacity-70">
          The robot is paid its service price; a reward above it stays in the contract.
        </span>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
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
