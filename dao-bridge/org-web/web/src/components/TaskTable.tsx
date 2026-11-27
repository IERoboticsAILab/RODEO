import { Task } from "../lib/types";
import { formatDuration, formatUnitsString } from "../lib/units";
import { describeTask } from "../lib/describe";

// 0x8464135c8F25Da09e49BC8782676a84730C318bC -> 0x8464…18bC (full address on hover)
function shortAddr(a: string): string {
  return a && a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

// allow extra fields produced by the fetch wrapper
type TaskRow = Task & { rewardToken?: string | number; rewardIec?: string | number; rewardWei?: string | number };
function statusLabel(status: number): string {
  switch (status) {
    case 0:
      return "Unassigned";
    case 1:
      return "Assigned";
    case 2:
      return "Executed";
    default:
      return String(status);
  }
}

// color helpers
const STATUS_BG: Record<number, string> = {
  0: "#fc9272", // Unassigned
  1: "#9ecae1", // Assigned
  2: "#a1d99b", // Executed
};

const YES_BG = "#a1d99b";
const NO_BG  = "#fc9272";

const badgeStyle = (bg: string): React.CSSProperties => ({
  backgroundColor: bg,
  color: "#111827",           // readable dark text
});

// Only tasks whose category has a time limit (e.g. Logistics) show anything here.
// Unassigned: the limit that starts when a robot takes it. Assigned: time left until
// the contract's deadline, or "proof in time". Executed: the limit it had.
function TimeLimit({ row }: { row: TaskRow }) {
  if (!row.timeoutS) return null;
  const limit = formatDuration(row.timeoutS);
  if (row.status !== 1 || row.deadline == null) {
    return <span title="execution time limit, counted from the assignment">{limit}</span>;
  }
  const at = new Date(row.deadline * 1000).toLocaleTimeString();
  if (row.proofInTime) {
    return <span className="badge" style={badgeStyle(YES_BG)} title={`limit ${limit}, deadline ${at}`}>proof in time</span>;
  }
  const left = row.secondsLeft ?? 0;
  if (left < 0) {
    return <span className="badge" style={badgeStyle(NO_BG)} title={`deadline ${at}: the oracle unassigns it shortly`}>timed out</span>;
  }
  return (
    <span className="badge" style={badgeStyle(left < 120 ? "#fdd0a2" : "#e5e7eb")} title={`limit ${limit}, deadline ${at}`}>
      {formatDuration(left)} left
    </span>
  );
}

// an assigned task (e.g. one the robot failed) is unassigned first: that frees the
// robot's service, refunds the creator and deactivates the task
export type TaskAction = "remove" | "activate" | "unassign";

export default function TaskTable({
  rows,
  onAction,
}: { rows: TaskRow[]; onAction?: (id: number, action: TaskAction) => void }) {
  return (
    <div className="card overflow-x-auto">
      <table className="table">
        <thead>
          <tr className="tr bg-gray-50 dark:bg-neutral-900">
            <th className="th">ID</th>
            <th className="th">Reward</th>
            <th className="th">Category</th>
            <th className="th">Type</th>
            <th className="th">Details</th>
            <th className="th">Creator</th>
            <th className="th">Executor</th>
            <th className="th">Status</th>
            <th className="th">Time limit</th>
            <th className="th">Active</th>
            <th className="th">Verified</th>
            <th className="th">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const token =
              row.rewardToken != null
                ? String(row.rewardToken)
                : row.rewardIec != null
                ? String(row.rewardIec)
                : row.rewardWei != null
                ? formatUnitsString(row.rewardWei, 18, 4)
                : "0";
                const action: TaskAction = row.status === 1 ? "unassign" : row.active ? "remove" : "activate";
                const label = row.status === 1 ? "Unassign" : row.active ? "Deactivate" : "Activate";
            return (
              <tr key={row.id} className="tr">
                <td className="td">{row.id}</td>
                <td className="td whitespace-nowrap">{token} IEC</td> {/* show token value */}
                <td className="td">{row.taskCategory}</td>
                <td className="td">{row.taskType}</td>
                <td className="td max-w-[16rem] truncate" title={describeTask((row as any).description ?? "")}>
                  {describeTask((row as any).description ?? "")}
                </td>
                <td className="td font-mono text-xs whitespace-nowrap" title={row.creator}>{shortAddr(row.creator)}</td>
                <td className="td font-mono text-xs whitespace-nowrap" title={row.executor}>{shortAddr(row.executor)}</td>
                <td className="td"><span className="badge" style={badgeStyle(STATUS_BG[row.status] ?? "#e5e7eb")}>{statusLabel(row.status)}</span></td>
                <td className="td whitespace-nowrap"><TimeLimit row={row} /></td>
                <td className="td">
                  <span className="badge" style={badgeStyle(row.active ? YES_BG : NO_BG)}>{row.active ? "Yes" : "No"}</span>
                </td>
                <td className="td">
                  <span className="badge" style={badgeStyle(row.verified ? YES_BG : NO_BG)}>{row.verified ? "Yes" : "No"}</span>
                </td>
                <td className="td">
                  <div className="flex gap-2">
                    <button className="btn focus-ring" onClick={() => onAction && onAction(row.id, action)}>{label}</button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
