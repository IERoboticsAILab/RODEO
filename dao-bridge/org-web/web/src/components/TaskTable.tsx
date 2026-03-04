import { Task } from "../lib/types";
import { formatUnitsString } from "../lib/units";

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

export default function TaskTable({
  rows,
  onAction,
}: { rows: TaskRow[]; onAction?: (id: number, action: "remove" | "activate") => void }) {
  return (
    <div className="card overflow-hidden">
      <table className="table">
        <thead>
          <tr className="tr bg-gray-50 dark:bg-neutral-900">
            <th className="th">ID</th>
            <th className="th">Reward</th>
            <th className="th">Category</th>
            <th className="th">Type</th>
            <th className="th">Creator</th>
            <th className="th">Executor</th>
            <th className="th">Status</th>
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
                const action = row.active ? "remove" : "activate";
                const label = row.active ? "Deactivate" : "Activate";
            return (
              <tr key={row.id} className="tr">
                <td className="td">{row.id}</td>
                <td className="td">{token} IEC</td> {/* show token value */}
                <td className="td">{row.taskCategory}</td>
                <td className="td">{row.taskType}</td>
                <td className="td">{row.creator}</td>
                <td className="td">{row.executor}</td>
                <td className="td"><span className="badge" style={badgeStyle(STATUS_BG[row.status] ?? "#e5e7eb")}>{statusLabel(row.status)}</span></td>
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
