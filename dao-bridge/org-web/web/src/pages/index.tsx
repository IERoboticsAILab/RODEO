
import Shell from "../components/Shell";
import Link from "next/link";
import useSWR from "swr";
import { fetchAll,  deleteService, deleteTask, activateService, activateTask, setServiceBusy, fetchTokenHolders } from "../lib/api";
import ServiceTable from "../components/ServiceTable";
import TaskTable from "../components/TaskTable";

export default function Home() {
  const { data, mutate } = useSWR("overview", fetchAll, { refreshInterval: 3000 });
  const { data: tokenData } = useSWR("tokenHolders", fetchTokenHolders, { refreshInterval: 10000 });
  const taskCount = data?.allTasks?.length ?? 0;
  const serviceCount = data?.allServices?.length ?? 0;
  
  async function handleServiceAction(
  id: number | string,
  action: "remove" | "activate" | "busy-on" | "busy-off"
) {
  const sid = Number(id);
  if (action === "remove") {
    await deleteService(sid);
  } else if (action === "activate") {
    await activateService(sid);
  } else if (action === "busy-on") {
    await setServiceBusy(sid, true);
  } else if (action === "busy-off") {
    await setServiceBusy(sid, false);
  }
  await mutate();
}

  async function handleTaskAction(id: number | string, action: "remove" | "activate") {
  if (action === "remove") {
    await deleteTask(Number(id));
  } else if (action === "activate") {
    await activateTask(Number(id));
  }
  await mutate();
}

const symbol = tokenData?.token?.symbol ?? "IEC";

  return (
    <Shell>
{/* Top section: left = 1/3, right = 2/3 */}
<div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
  {/* Left 1/3 */}
  <div className="lg:col-span-1 self-start">
    <div className="flex gap-4">
      {/* Counters with just enough width for three digits */}
      <div className="card p-6 flex-none min-w-[8rem] flex flex-col items-center text-center">
        <div className="text-lg text-gray-500">Tasks</div>
        <div className="flex-1 w-full flex items-center justify-center">
          <div className="text-5xl font-semibold leading-none">{taskCount}</div>
        </div>
      </div>
      <div className="card p-6 flex-none min-w-[8rem] flex flex-col items-center text-center">
        <div className="text-lg text-gray-500">Services</div>
        <div className="flex-1 w-full flex items-center justify-center">
          <div className="text-5xl font-semibold leading-none">{serviceCount}</div>
      </div>
      </div>

      {/* Actions takes the remaining space */}
      <div className="card p-4 flex-1 flex flex-col items-center text-center">
        <div className="text-lg text-gray-500">Actions</div>
        <div className="mt-2 flex flex-wrap gap-2 justify-center">
          <Link href="/tasks" className="btn focus-ring">Manage tasks</Link>
          <Link href="/services" className="btn focus-ring">Manage services</Link>
        </div>
      </div>
    </div>
  </div>

  {/* Right 2/3 */}
<div className="lg:col-span-2">
  <div className="card p-4">
    <h2 className="text-lg font-semibold mb-2">Wallets and IECoin</h2>

    {!tokenData && (
      <p className="text-sm text-gray-500">Loading wallet balances…</p>
    )}

    {tokenData && tokenData.holders.length === 0 && (
      <p className="text-sm text-gray-500">No wallets with a balance yet</p>
    )}

    {tokenData && tokenData.holders.length > 0 && (
      <div className="overflow-x-auto">
        {/* limit height to about four rows, allow vertical scroll */}
        <div className="max-h-64 overflow-y-auto pr-1">
          <table className="table">
            <thead>
              <tr className="tr bg-gray-50 dark:bg-neutral-900">
                <th className="th">Address</th>
                <th className="th text-right">Balance</th>
                <th className="th w-24 text-right">Copy</th>
              </tr>
            </thead>
            <tbody>
              {tokenData.holders.map(h => (
                <tr key={h.address} className="tr">
                  <td className="td">
                    <span className="font-mono text-sm truncate" title={h.address}>{h.address}</span>
                  </td>
                  <td className="td text-right">
                    <span className="font-medium">{h.balance} {symbol}</span>
                  </td>
                  <td className="td text-right">
                    <button
                      className="btn focus-ring text-xs"
                      onClick={() => navigator.clipboard.writeText(h.address)}
                      aria-label={`Copy ${h.address}`}
                      title="Copy address"
                    >
                      Copy
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
</div>
      </div>
{/* All services and all tasks */}
<section className="mt-8 space-y-8">
  <div className="space-y-2">
    <h2 className="font-semibold">All services</h2>
    <ServiceTable
      rows={data?.allServices ?? []}
      onAction={handleServiceAction}
    />
  </div>

  <div className="space-y-2">
    <h2 className="font-semibold">All tasks</h2>
    <TaskTable
      rows={data?.allTasks ?? []}
      onAction={handleTaskAction}
    />
  </div>
</section>
    </Shell>
  );
}
