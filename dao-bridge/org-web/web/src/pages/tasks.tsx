// src/pages/tasks.tsx
import Shell from "../components/Shell";
import { CreateTaskForm, TaskRequest } from "../components/Forms";
import TaskTable from "../components/TaskTable";
import { createTask, deleteTask, fetchTasks, activateTask, fetchCatalog } from "../lib/api";
import useSWR from "swr";

export default function TasksPage() {
  const { data, mutate } = useSWR("tasks", fetchTasks, { refreshInterval: 3000 });
  const { data: catalog } = useSWR("catalog", fetchCatalog, { refreshInterval: 3000 });

  async function handleCreate(req: TaskRequest) {
    await createTask(req);          // errors are shown by the form
    await mutate();
  }

  async function handleAction(id: number | string, action: "remove" | "activate") {
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
        <div className="card p-4">
          <CreateTaskForm catalog={catalog} onCreate={handleCreate} />
        </div>

        <section className="space-y-2">
          <h2 className="font-semibold">My tasks</h2>
          <TaskTable rows={data?.mine ?? []} onAction={handleAction} />
        </section>
      </div>
    </Shell>
  );
}
