// Readable parts of a task description. RODEO v2 tasks carry
// {"v":1,"title":"...","params":{...},"note":"..."}; older tasks are free text.
type Parsed = { title: string; details: string };

function parse(description: string): Parsed {
  try {
    const d = JSON.parse(description);
    if (d && typeof d === "object" && typeof d.v === "number") {
      const params = Object.entries(d.params ?? {}).map(([k, v]) => `${k}=${v}`).join(", ");
      return { title: String(d.title ?? ""), details: [params, d.note].filter(Boolean).join(" · ") };
    }
  } catch {
    /* free text */
  }
  return { title: "", details: description || "" };
}

export function taskTitle(description: string): string {
  return parse(description).title || "-";
}

export function taskDetails(description: string): string {
  return parse(description).details || "-";
}

// title and details together, for places with a single column
export function describeTask(description: string): string {
  const p = parse(description);
  return [p.title, p.details].filter(Boolean).join(": ") || "-";
}
