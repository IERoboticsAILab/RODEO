// src/pages/proofs.tsx
import { useState } from "react";
import Shell from "../components/Shell";
import useSWR from "swr";
import { api } from "../lib/api";
import { Task } from "../lib/types";
import { formatUnitsString } from "../lib/units";

export default function ProofsPage() {
  const { data: tasks, mutate } = useSWR<Task[]>("assignedTasks", api.tasks.assigned, { refreshInterval: 3000 });
  const [proofURI, setProofURI] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<string>("");

  async function submit(taskId: number) {
    try {
      setBusyId(taskId);
      setMessage("");
      const res = await api.tasks.submitProof(taskId, proofURI);
      setMessage(`Submitted. Tx: ${res.txHash}`);
      setProofURI("");
      await mutate();
    } catch (e: any) {
      setMessage(e?.message ?? String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Shell>
      <div className="space-y-6">
        <section className="space-y-2">
          <h1 className="text-2xl font-semibold">Submit proof as organization executor</h1>
          <p className="text-sm text-muted-foreground">
            Paste a path or URL that points to your proof. Then click submit on a task below.
          </p>
          <div className="flex gap-2 max-w-3xl">
            <input
              type="text"
              className="input flex-1 focus-ring"
              placeholder="https://example.com/proofs/task-123.txt or /ipfs/Qm..."
              value={proofURI}
              onChange={(e) => setProofURI(e.target.value)}
            />
          </div>
          {message && <div className="text-sm">{message}</div>}
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Assigned tasks where executor is the organization</h2>
          <div className="overflow-x-auto border rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/40">
                  <th className="th">ID</th>
                  <th className="th">Description</th>
                  <th className="th">Category</th>
                  <th className="th">Type</th>
                  <th className="th">Reward</th>
                  <th className="th">Status</th>
                  <th className="th">Proof</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(tasks ?? []).map((t) => {
                  const reward = t.rewardWei ? formatUnitsString(t.rewardWei, 18, 4) : "0";
                  return (
                    <tr key={t.id} className="border-t">
                      <td className="td">{t.id}</td>
                      <td className="td">{t.description}</td>
                      <td className="td">{t.taskCategory}</td>
                      <td className="td">{t.taskType}</td>
                      <td className="td">{reward}</td>
                      <td className="td">{t.status === 1 ? "Assigned" : String(t.status)}</td>
                      <td className="td break-all">{t.proofURI || "None"}</td>
                      <td className="td">
                        <button
                          className="btn btn-default focus-ring"
                          onClick={() => submit(t.id)}
                          disabled={!proofURI || busyId === t.id}
                          title={!proofURI ? "Enter a proof URI above" : "Submit proof"}
                        >
                          {busyId === t.id ? "Submitting..." : "Submit using field"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {(!tasks || tasks.length === 0) && (
                  <tr>
                    <td className="td" colSpan={8}>
                      No assigned tasks for the organization.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Shell>
  );
}