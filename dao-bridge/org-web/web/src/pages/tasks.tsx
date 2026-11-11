// src/pages/tasks.tsx
import Shell from "../components/Shell";
import { CreateTaskForm, TaskRequest } from "../components/Forms";
import TaskTable from "../components/TaskTable";
import { createTask, deleteTask, fetchTasks, activateTask, fetchCatalog, prepareTask, fetchTasksByCreator } from "../lib/api";
import { shortAddress, useWallet } from "../lib/wallet";
import useSWR from "swr";

export default function TasksPage() {
  const wallet = useWallet();
  const { data, mutate } = useSWR("tasks", fetchTasks, { refreshInterval: 3000 });
  const { data: catalog } = useSWR("catalog", fetchCatalog, { refreshInterval: 3000 });
  // with a wallet connected, "My tasks" are the ones that wallet posted
  const { data: walletTasks, mutate: mutateWalletTasks } = useSWR(
    wallet.address ? ["tasks", wallet.address] : null, () => fetchTasksByCreator(wallet.address!),
    { refreshInterval: 3000 });

  async function handleCreate(req: TaskRequest) {
    // errors are shown by the form
    if (wallet.connected) {
      if (!wallet.onRightChain) throw new Error(`switch MetaMask to ${wallet.config?.chainName} first`);
      const prepared = await prepareTask(req);       // the backend checks it
      await wallet.postTask(prepared);               // the wallet approves the reward and posts it
      await mutateWalletTasks();
    } else {
      await createTask(req);                         // paid by the organization
    }
    await mutate();
  }

  async function handleAction(id: number | string, action: "remove" | "activate") {
    if (action === "remove" && !window.confirm(
        `Remove task ${id}? The contract does not refund its reward, and reactivating it later ` +
        `takes the reward again.`)) {
      return;
    }
    if (wallet.connected) {
      // tasks this wallet posted: only it may remove or reactivate them
      const row: any = (walletTasks ?? []).find((t: any) => Number(t.id) === Number(id));
      if (action === "remove") await wallet.removeTask(Number(id));
      else if (row) await wallet.activateTask(Number(id), String(row.rewardWei));
      await mutateWalletTasks();
      return;
    }
    if (action === "remove") {
      await deleteTask(Number(id));
    } else if (action === "activate") {
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
          <p className="text-xs opacity-70">
            {wallet.connected
              ? `Paid by your wallet ${shortAddress(wallet.address)}: MetaMask asks you to approve the reward, then to post the task.`
              : "Paid by the organization. Connect a wallet (top right) to post and pay from your own wallet."}
          </p>
          <CreateTaskForm catalog={catalog} onCreate={handleCreate} />
        </div>


        <section className="space-y-2">
          <h2 className="font-semibold">
            {wallet.connected ? `My tasks (${shortAddress(wallet.address)})` : "Organization's tasks"}
          </h2>
          <TaskTable rows={(wallet.connected ? walletTasks : data?.mine) ?? []} onAction={handleAction} />
        </section>
      </div>
    </Shell>
  );
}
