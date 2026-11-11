// Readable form of a task description. RODEO v2 tasks carry
// {"v":1,"params":{...},"note":"..."}; older tasks are free text.
export function describeTask(description: string): string {
  try {
    const d = JSON.parse(description);
    if (d && typeof d === "object" && typeof d.v === "number") {
      const params = Object.entries(d.params ?? {}).map(([k, v]) => `${k}=${v}`).join(", ");
      return [params, d.note].filter(Boolean).join(" · ") || "-";
    }
  } catch {
    /* free text */
  }
  return description || "-";
}
