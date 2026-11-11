// src/pages/tasks.tsx
import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { CreateTaskForm, TaskRequest } from "../components/Forms";
import TaskTable from "../components/TaskTable";
import { createTask, deleteTask, fetchTasks, activateTask, fetchCatalog, prepareTask, fetchTasksByCreator } from "../lib/api";
import { shortAddress, useWallet } from "../lib/wallet";
import { useAdmin } from "../lib/admin";
import useSWR from "swr";

type Payer = "wallet" | "org";

const REMOVE_WARNING = (id: number | string) =>
  `Remove task ${id}? The contract does not refund its reward, and reactivating it later takes the reward again.`;

export default function TasksPage() {
  const wallet = useWallet();
  const admin = useAdmin();
  const { data, mutate } = useSWR("tasks", fetchTasks, { refreshInterval: 3000 });
  const { data: catalog } = useSWR("catalog", fetchCatalog, { refreshInterval: 3000 });
  const { data: walletTasks, mutate: mutateWalletTasks } = useSWR(
    wallet.address ? ["tasks", wallet.address] : null, () => fetchTasksByCreator(wallet.address!),
    { refreshInterval: 3000 });

  // who pays: the connected wallet, or (admin only) the organization
  const canWallet = wallet.connected;
  const canOrg = admin.unlocked;
  const [payer, setPayer] = useState<Payer>("wallet");
  useEffect(() => {
    if (payer === "wallet" && !canWallet && canOrg) setPayer("org");
    if (payer === "org" && !canOrg && canWallet) setPayer("wallet");
  }, [payer, canWallet, canOrg]);

  async function handleCreate(req: TaskRequest) {
    // errors are shown by the form
    if (payer === "wallet") {
      if (!wallet.connected) throw new Error("connect MetaMask first");
      if (!wallet.onRightChain) throw new Error(`switch MetaMask to ${wallet.config?.chainName} first`);
      const prepared = await prepareTask(req);       // the backend checks it
      await wallet.postTask(prepared);               // the wallet approves the reward and posts it
      await mutateWalletTasks();
    } else {
      await createTask(req);                         // the organization pays (admin PIN required)
      await mutate();
    }
  }

  // tasks this wallet posted: only the wallet may remove or reactivate them
  async function walletAction(id: number | string, action: "remove" | "activate") {
    if (action === "remove") {
      if (!window.confirm(REMOVE_WARNING(id))) return;
      await wallet.removeTask(Number(id));
    } else {
      const row: any = (walletTasks ?? []).find((t: any) => Number(t.id) === Number(id));
      if (row) await wallet.activateTask(Number(id), String(row.rewardWei));
    }
    await mutateWalletTasks();
  }

  // the organization's tasks: signed by the console (admin PIN required)
  async function orgAction(id: number | string, action: "remove" | "activate") {
    if (action === "remove") {
      if (!window.confirm(REMOVE_WARNING(id))) return;
      await deleteTask(Number(id));
    } else {
      await activateTask(Number(id));
    }
    await mutate();
  }

  return (
    <Shell>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Tasks</h1>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div className="card p-4 space-y-3">
          {!canWallet && !canOrg ? (
            <p className="text-sm">
              <span className="font-semibold">Connect MetaMask</span> (top right) to post tasks and pay with your own wallet.
              {admin.enabled ? " The organization's wallet is for admins (Home page)." : ""}
            </p>
          ) : (
            <>
              {canWallet && canOrg ? (
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <span className="font-semibold">Pay from:</span>
                  <label className="flex items-center gap-1">
                    <input type="radio" checked={payer === "wallet"} onChange={() => setPayer("wallet")} />
                    my wallet {shortAddress(wallet.address)}
                  </label>
                  <label className="flex items-center gap-1">
                    <input type="radio" checked={payer === "org"} onChange={() => setPayer("org")} />
                    the organization (admin)
                  </label>
                </div>
              ) : (
                <p className="text-xs opacity-70">
                  {payer === "wallet"
                    ? `Paid by your wallet ${shortAddress(wallet.address)}: MetaMask asks you to approve the reward, then to post the task.`
                    : "Paid by the organization (admin)."}
                </p>
              )}
              <CreateTaskForm catalog={catalog} onCreate={handleCreate} />
            </>
          )}
        </div>

        {canWallet ? (
          <section className="space-y-2">
            <h2 className="font-semibold">My tasks ({shortAddress(wallet.address)})</h2>
            <TaskTable rows={walletTasks ?? []} onAction={walletAction} />
          </section>
        ) : null}

        {canOrg ? (
          <section className="space-y-2">
            <h2 className="font-semibold">Organization's tasks</h2>
            <TaskTable rows={data?.mine ?? []} onAction={orgAction} />
          </section>
        ) : null}
      </div>
    </Shell>
  );
}
