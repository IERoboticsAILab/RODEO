import Shell from "../components/Shell";

export default function Guide() {
  return (
    <Shell>
      <h1 className="text-2xl font-semibold tracking-tight mb-4">Style guide</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4 space-y-3">
          <h2 className="font-semibold">Buttons</h2>
          <div className="flex gap-2">
            <button className="btn btn-primary">Primary</button>
            <button className="btn">Default</button>
            <button className="btn btn-ghost">Ghost</button>
          </div>
        </div>
        <div className="card p-4 space-y-3">
          <h2 className="font-semibold">Inputs</h2>
          <div className="space-y-2">
            <label className="label">Label</label>
            <input className="input" placeholder="Write something" />
          </div>
        </div>
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Colors</h2>
          <div className="grid grid-cols-5 gap-2">
            {["#a6bddb", "#ece2f0", "#111827", "#374151", "#9CA3AF"].map((c) => (
              <div key={c} className="rounded-xl border border-gray-200 dark:border-gray-800 p-3 text-xs" style={{ backgroundColor: c }}>
                {c}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Shell>
  );
}