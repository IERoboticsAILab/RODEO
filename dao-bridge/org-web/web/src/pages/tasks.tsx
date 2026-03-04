// src/pages/tasks.tsx
import { useState } from "react";
import Shell from "../components/Shell";
import { CreateTaskForm } from "../components/Forms";
import TaskTable from "../components/TaskTable";
import { createTask, deleteTask, fetchTasks, activateTask } from "../lib/api";
import useSWR from "swr";

export default function TasksPage() {
  const { data, mutate } = useSWR("tasks", fetchTasks, { refreshInterval: 3000 });

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [type, setType] = useState("");
  const [reward, setReward] = useState(100);

  async function handleCreate(_: any) {
    if (reward <= 0) {
      alert("Reward must be greater than 0");
      return;
    }
    const payload = {
      description,
      category: category || "general",
      taskType: type || "default",
      rewardIec: reward,
    };
    await createTask(payload);
    await mutate();
    setTitle("");
    setDescription("");
    setCategory("");
    setType("");
    setReward(100);
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
          <CreateTaskForm
            onCreate={handleCreate}
            setTitle={setTitle}
            setDescription={setDescription}
            setCategory={setCategory}
            setType={setType}
            setReward={setReward}
            title={title}
            description={description}
            category={category}
            type={type}
            reward={reward}
          />
        </div>

        
          <section className="space-y-2">
            <h2 className="font-semibold">My tasks</h2>
            <TaskTable rows={data?.mine ?? []} onAction={handleAction} />
          </section>
        </div>
    </Shell>
  );
}
