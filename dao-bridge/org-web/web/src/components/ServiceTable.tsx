import { Service } from "../lib/types";
import { formatUnitsString } from "../lib/units";

type ServiceRow = Service & {
  // optional normalized fields added by fetch wrappers
  priceToken?: string | number;
  priceIec?: string | number;
  priceWei?: string | number;
  owner?: string;
};

function priceLabel(row: ServiceRow): string {
  if (row.priceToken != null) return String(row.priceToken);
  if (row.priceIec != null) return String(row.priceIec);
  if (row.priceWei != null) return formatUnitsString(row.priceWei, 18, 4);
  if ((row as any).price != null) return String((row as any).price);
  return "0";
}

// colors
const YES_BG = "#a1d99b";
const NO_BG  = "#fc9272";

const badgeStyle = (bg: string): React.CSSProperties => ({
  backgroundColor: bg,
  color: "#111827",
});

export default function ServiceTable({
  rows,
  onAction,
}: {
  rows: ServiceRow[];
  onAction?: (id: number, action: "remove" | "activate" | "busy-on" | "busy-off") => void;
}) {
  return (
    <div className="card overflow-hidden">
      <table className="table">
        <thead>
          <tr className="tr bg-gray-50 dark:bg-neutral-900">
            <th className="th">ID</th>
            <th className="th">Name</th>
            <th className="th">Price</th>
            <th className="th">Category</th>
            <th className="th">Type</th>
            <th className="th w-[15rem]">Owner</th>
            <th className="th w-20 text-center">Active</th>
            <th className="th w-2 text-center">Status</th>
            <th className="th !text-center w-[16rem]">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const activeAction  = row.active ? "remove" : "activate";
            const activeLabel  = row.active ? "Deactivate" : "Activate";
            const busyAction = row.busy ? "busy-off" : "busy-on";
            const busyLabel = row.busy ? "Set-Free" : "Set-Busy";
            return (
              <tr key={row.id} className="tr">
                <td className="td">{row.id}</td>
                <td className="td">{row.name ?? (row as any).serviceName ?? ""}</td>
                <td className="td">{priceLabel(row)} IEC</td>
                <td className="td">{row.serviceCategory ?? ""}</td>
                <td className="td">{row.serviceType}</td>
                <td className="td">{row.owner ?? row.creator}</td>
                <td className="td">
                  <span className="badge" style={badgeStyle(row.active ? YES_BG : NO_BG)}>{row.active ? "Yes" : "No"}</span>
                </td>
                <td className="td">
                  <span className="badge" style={badgeStyle(row.busy ? NO_BG : YES_BG)}>{row.busy ? "Busy" : "Free"}</span>
                </td>
                <td className="td min-w-[12rem]">
                  <div className="flex justify-center gap-2">
                    <button
                      className="btn focus-ring"
                      onClick={() => onAction && onAction(row.id, busyAction)}
                    >
                      {busyLabel}
                    </button>
                    <button
                      className="btn focus-ring"
                      onClick={() => onAction && onAction(row.id, activeAction)}
                    >
                      {activeLabel}
                    </button>
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
